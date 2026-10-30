"""Upload pipeline: extract, chunk, tag, embed and save a file, as a resumable background job or inline (chat)."""
import hashlib
import logging
import threading
from typing import Optional

from psycopg2.extras import Json

from core.database import db_cursor
from core.sources import SOURCE_IDS, TAG_STYLES
from services.chunk_service import embed_chunks, replace_chunks
from services.chunker import chunk_document
from services import upload_jobs
from services.tagging_service import generate_chunk_summaries, generate_chunk_tags, generate_document_metadata

logger = logging.getLogger(__name__)


def list_uploads() -> list[dict]:
    """Running and recently failed upload jobs, each with its source's accent color for the UI."""
    return [{**u, "color": TAG_STYLES[SOURCE_IDS[u["source"]]][2]} for u in upload_jobs.list_jobs()]


def _is_unchanged(cur, file_name: str, file_hash: str, source_id: str, session_id: Optional[str]) -> bool:
    cur.execute(
        """SELECT 1 FROM documents
           WHERE filename = %s AND file_hash = %s AND source_id = %s
             AND session_id IS NOT DISTINCT FROM %s AND status = 'ready'""",
        (file_name, file_hash, source_id, session_id),
    )
    return cur.fetchone() is not None


def process_and_save_document(file_name: str, content: bytes, content_type: str, source_id: str, session_id: str = None,
                              job: Optional[upload_jobs.UploadJob] = None) -> str:
    """Extract, chunk, embed and store a file, reporting progress to job if given. Returns a status message."""
    # Untracked (chat): results live in memory only. Tracked: results saved so far are reused, not regenerated.
    job = job or upload_jobs.UploadJob(file_name, "")
    is_tool = source_id == SOURCE_IDS['tools']
    if is_tool:
        session_id = None  # tool documents are global
    # A resumed job has no file content, only the hash stored when it started
    file_hash = job.file_hash or hashlib.sha256(content).hexdigest()

    # Cheap duplicate check first, so a re-upload skips the slow extraction below
    with db_cursor() as cur:
        if _is_unchanged(cur, file_name, file_hash, source_id, session_id):
            return f"File {file_name} already exists (duplicate not saved)"

    if job.chunks is None:
        job.set_chunks(chunk_document(content, content_type, file_name))
    chunks = job.chunks
    if not chunks:
        return f"File {file_name} has no extractable text (not saved)"

    # Slow work (LLM tagging, embedding) happens before the write transaction opens
    texts = [c["text"] for c in chunks]
    job.begin()
    if is_tool:
        if job.doc_metadata is None:
            job.stage = "Generating metadata"
            job.set_doc_metadata(generate_document_metadata("\n\n".join(texts)))
        job.stage = "Tagging chunks"
        _fill_missing(job.tags, texts, generate_chunk_tags, job.set_tags)
    job.stage = "Summarizing chunks"
    _fill_missing(job.summaries, texts, generate_chunk_summaries, job.set_summary)
    doc_metadata, chunk_tags, summaries = job.doc_metadata, job.tags, job.summaries
    # Chunk i stores the summary of chunk i-1; the first chunk has none
    previous_summaries = [None] + summaries[:-1]
    job.stage = "Embedding"
    embeddings, embedded_from = embed_chunks(chunks, summaries)

    job.check_cancelled()
    job.stage = "Saving"
    with db_cursor() as cur:
        # Replaces a saved document of that name, or this job's own 'uploading' one, never another upload's
        cur.execute(
            """INSERT INTO documents (filename, file_hash, source_id, session_id, metadata, status)
               VALUES (%s, %s, %s, %s, %s, 'ready')
               ON CONFLICT (filename) DO UPDATE SET
                   file_hash = EXCLUDED.file_hash, source_id = EXCLUDED.source_id,
                   session_id = EXCLUDED.session_id, metadata = EXCLUDED.metadata, status = 'ready',
                   content = NULL
               WHERE documents.status = 'ready' OR documents.id = %s
               RETURNING id""",
            (file_name, file_hash, source_id, session_id, Json(doc_metadata) if doc_metadata else None, job.id),
        )
        row = cur.fetchone()
        if row is None:
            return f"File {file_name} is already being uploaded (not saved)"
        replace_chunks(cur, row[0], chunks, embeddings, embedded_from, chunk_tags, previous_summaries)

    return f"File {file_name} uploaded successfully and saved to database"


def _fill_missing(results: list, texts: list[str], generate, save):
    """Generate results only for texts that have none yet, saving each as it finishes."""
    missing = [i for i, r in enumerate(results) if r is None]
    if missing:
        generate([texts[i] for i in missing], on_result=lambda j, r: save(missing[j], r))


def _process_in_background(job: upload_jobs.UploadJob):
    def work():
        try:
            upload_jobs.wait_turn(job)
            process_and_save_document(job.filename, job.content, job.content_type, SOURCE_IDS[job.source], job=job)
            upload_jobs.finish(job)
        except upload_jobs.Cancelled:
            logger.info("Upload of %s %s", job.filename, "paused" if job.paused else "cancelled")
        except Exception:
            if upload_jobs.stopping:
                return  # the server is going down; the job's rows stay and resume on next start
            logger.exception("Upload of %s failed", job.filename)
            upload_jobs.finish(job, error="Processing failed. Check the file type, or the server log for details.")
        finally:
            upload_jobs.leave_queue(job)

    upload_jobs.enqueue(job)
    job.worker = threading.Thread(target=work, daemon=True)
    job.worker.start()


def start_upload(file_name: str, content: bytes, content_type: str, source: str) -> Optional[dict]:
    """Process an upload in the background; its progress is listed by upload_jobs.list_jobs until it finishes.

    Returns None for a file already saved unchanged. Raises UploadInProgress if that filename is uploading.
    """
    file_hash = hashlib.sha256(content).hexdigest()
    # Checked before create, which would otherwise overwrite the saved document
    with db_cursor() as cur:
        if _is_unchanged(cur, file_name, file_hash, SOURCE_IDS[source], None):
            return None
    job = upload_jobs.create(file_name, source, SOURCE_IDS[source], content, content_type, file_hash)
    if job is None:
        raise UploadInProgress(f"{file_name} is already being uploaded.")
    _process_in_background(job)
    return job.to_dict()


class UploadInProgress(Exception):
    pass


def pause_upload(job_id: int) -> bool:
    """Stop a job's worker at its next saved result; its progress is kept for resume_upload."""
    job = upload_jobs.get(job_id)
    if job is None or job.error:
        return False
    job.paused = True
    return True


def resume_upload(job_id: int) -> Optional[str]:
    """Continue a paused job from its saved progress. Returns an error message, or None on success."""
    job = upload_jobs.get(job_id)
    if job is None or job.error:
        return "Upload not found"
    if job.worker and job.worker.is_alive():
        return "Upload is still pausing" if job.paused else None
    job.paused = False
    _process_in_background(job)
    return None


def resume_uploads():
    """Continue uploads a previous run left unfinished, from their last saved result."""
    for job in upload_jobs.load_unfinished({uuid: name for name, uuid in SOURCE_IDS.items()}):
        logger.info("Resuming upload of %s", job.filename)
        _process_in_background(job)
