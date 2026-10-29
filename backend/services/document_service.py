import hashlib
import logging
import threading
from typing import Optional

from psycopg2.extras import Json

from core.database import db_cursor
from services.chunk_service import embed_chunks, replace_chunks
from services.chunker import chunk_document
from services.display import format_metadata
from services import upload_jobs
from services.tagging_service import generate_chunk_summaries, generate_chunk_tags, generate_document_metadata

logger = logging.getLogger(__name__)

# Upload origins, keyed by the name clients send; values are source.uuid rows from schema.sql
SOURCE_IDS = {
    'library': '79279d88-e2c3-4a36-9da6-3f02dd71796b',
    'tools': 'b8118424-5418-47b7-a661-8bb768aa8ef5',
    'chat': '20a26963-d20c-469f-8837-620321d589a6'
}

# source uuid -> (label, background color, text color) for the document tag badge
TAG_STYLES = {
    SOURCE_IDS['chat']: ('Chat Interface', '#e0e7ff', '#4f46e5'),
    SOURCE_IDS['library']: ('Library', '#dcfce7', '#16a34a'),
    SOURCE_IDS['tools']: ('Tools', '#fef3c7', '#d97706'),
}


def get_upload_sources() -> list[dict]:
    """Sources a client may upload to (chat is implicit), with label and accent color for the UI."""
    return [
        {"value": name, "label": TAG_STYLES[SOURCE_IDS[name]][0], "color": TAG_STYLES[SOURCE_IDS[name]][2]}
        for name in ('library', 'tools')
    ]


def _is_unchanged(cur, file_name: str, file_hash: str, source_id: str, session_id: Optional[str]) -> bool:
    cur.execute(
        """SELECT 1 FROM documents
           WHERE filename = %s AND file_hash = %s AND source_id = %s
             AND session_id IS NOT DISTINCT FROM %s""",
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
    file_hash = hashlib.sha256(content).hexdigest()

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
        cur.execute(
            """INSERT INTO documents (filename, file_hash, source_id, session_id, metadata)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (filename) DO UPDATE SET
                   file_hash = EXCLUDED.file_hash, source_id = EXCLUDED.source_id,
                   session_id = EXCLUDED.session_id, metadata = EXCLUDED.metadata
               RETURNING id""",
            (file_name, file_hash, source_id, session_id, Json(doc_metadata) if doc_metadata else None),
        )
        replace_chunks(cur, cur.fetchone()[0], chunks, embeddings, embedded_from, chunk_tags, previous_summaries)

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
                return  # the server is going down; the job's row stays and resumes on next start
            logger.exception("Upload of %s failed", job.filename)
            upload_jobs.finish(job, error="Processing failed. Check the file type, or the server log for details.")
        finally:
            upload_jobs.leave_queue(job)

    upload_jobs.enqueue(job)
    job.worker = threading.Thread(target=work, daemon=True)
    job.worker.start()


def start_upload(file_name: str, content: bytes, content_type: str, source: str) -> dict:
    """Process an upload in the background; its progress is listed by upload_jobs.list_jobs until it finishes."""
    job = upload_jobs.create(file_name, source, content, content_type)
    _process_in_background(job)
    return job.to_dict()


def pause_upload(job_id: str) -> bool:
    """Stop a job's worker at its next saved result; its progress is kept for resume_upload."""
    job = upload_jobs.get(job_id)
    if job is None or job.error:
        return False
    job.paused = True
    return True


def resume_upload(job_id: str) -> Optional[str]:
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
    for job in upload_jobs.load_unfinished():
        logger.info("Resuming upload of %s", job.filename)
        _process_in_background(job)


def get_all_documents(search: str = ""):
    # Escape LIKE wildcards so the search matches the filename text literally
    pattern = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with db_cursor() as cur:
        cur.execute("""
            SELECT d.id, d.filename, d.source_id, s.source_name, d.metadata
            FROM documents d
            LEFT JOIN source s ON d.source_id = s.uuid
            WHERE d.filename ILIKE %s
            ORDER BY d.id DESC
        """, (pattern,))
        rows = cur.fetchall()
    docs = []
    for doc_id, filename, source_id, source_name, metadata in rows:
        label, bg_color, text_color = TAG_STYLES.get(source_id, (source_name or "unknown", '#f1f5f9', '#64748b'))
        docs.append({
            "id": doc_id,
            "filename": filename,
            "tag_label": label,
            "tag_bg_color": bg_color,
            "tag_text_color": text_color,
            "metadata_text": format_metadata(metadata, "No metadata available for this document."),
        })
    return docs


def get_document_names(session_id: str = None) -> list[str]:
    """Filenames visible to a chat: global documents plus that session's attachments."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT filename FROM documents WHERE session_id IS NULL OR session_id = %s ORDER BY id DESC",
            (session_id,),
        )
        return [row[0] for row in cur.fetchall()]


def delete_document(doc_id: int) -> bool:
    # chunks go with it via ON DELETE CASCADE
    with db_cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s RETURNING id", (doc_id,))
        return cur.fetchone() is not None
