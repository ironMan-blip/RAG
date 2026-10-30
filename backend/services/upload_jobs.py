import mimetypes
import threading
import time
from typing import Optional

from psycopg2.extras import Json, execute_values

from core.database import db_cursor

# Failed jobs stay listed this long so the Library can show why; finished ones leave at once
FAILED_TTL_SECONDS = 600

# Jobs of this process, keyed by document id: running, or failed and still listed. The document's row and its
# chunk rows (status 'uploading') are the durable copy.
_jobs: dict[int, "UploadJob"] = {}
_lock = threading.Lock()

# Set on shutdown: a worker dying then is paused, not failed, so its rows stay for resume
stopping = False

# Background jobs in upload order; only the first one is processed, the rest wait their turn
_queue: list["UploadJob"] = []
_turn = threading.Condition()


class Cancelled(Exception):
    """Raised in a worker whose job was cancelled or paused, to stop it at the next saved result."""


class UploadJob:
    """One document being processed and every result finished so far.

    A tracked job (id = its document's id) mirrors the file and each result to its 'uploading' document and its
    chunk rows, so a restart resumes from there. An untracked job (chat attachments) only keeps them in memory.
    """

    def __init__(self, filename: str, source: str, content: bytes = b"", content_type: Optional[str] = None,
                 id: Optional[int] = None, file_hash: Optional[str] = None, chunks: Optional[list] = None,
                 chunk_ids: Optional[list[int]] = None, doc_metadata: Optional[dict] = None,
                 tags: Optional[list] = None, summaries: Optional[list] = None):
        self.id = id
        self.filename = filename
        self.source = source
        self.content = content
        self.content_type = content_type
        self.file_hash = file_hash
        self.chunks = chunks  # None until extraction finishes
        self.chunk_ids = chunk_ids  # chunk row per chunk, tracked jobs only
        self.doc_metadata = doc_metadata
        self.tags = tags  # per chunk; None where not generated yet
        self.summaries = summaries
        self.stage = "Extracting text"
        self.error: Optional[str] = None
        self.failed_at: Optional[float] = None
        self.cancelled = False
        self.paused = False
        self.worker: Optional[threading.Thread] = None
        self._pace_start: Optional[tuple[float, int]] = None  # (time, done) when this process started working

    @property
    def total(self) -> int:
        """Work units: one per LLM call plus one for embedding; 0 until the chunk count is known."""
        if self.chunks is None:
            return 0
        n = len(self.chunks)
        return 2 * n + 2 if self.source == "tools" else n + 1

    @property
    def done(self) -> int:
        if self.chunks is None:
            return 0
        return ((self.doc_metadata is not None) + sum(t is not None for t in self.tags)
                + sum(s is not None for s in self.summaries))

    def check_cancelled(self):
        if self.cancelled or self.paused:
            raise Cancelled()

    def _update(self, sql: str, *params):
        self.check_cancelled()
        if self.id is not None:
            with db_cursor() as cur:
                cur.execute(sql, params)

    def set_chunks(self, chunks: list[dict]):
        self.chunks, self.tags, self.summaries = chunks, [None] * len(chunks), [None] * len(chunks)
        self.check_cancelled()
        if self.id is not None and chunks:
            with db_cursor() as cur:
                execute_values(
                    cur, "INSERT INTO chunks (doc_id, chunk_text, metadata, status) VALUES %s",
                    [(self.id, c["text"], Json({k: v for k, v in c.items() if k != "text"}), "incomplete")
                     for c in chunks],
                )
                cur.execute("SELECT chunk_id FROM chunks WHERE doc_id = %s ORDER BY chunk_id", (self.id,))
                self.chunk_ids = [row[0] for row in cur.fetchall()]

    def set_doc_metadata(self, metadata: dict):
        self.doc_metadata = metadata
        self._update("UPDATE documents SET metadata = %s WHERE id = %s", Json(metadata), self.id)

    def _set_chunk_field(self, i: int, key: str, value):
        """Keep a result in the chunk row's metadata until the final save writes the chunk properly."""
        complete = self.summaries[i] is not None and (self.source != "tools" or self.tags[i] is not None)
        self._update("UPDATE chunks SET metadata = metadata || %s, status = %s WHERE chunk_id = %s",
                     Json({key: value}), "complete" if complete else "incomplete",
                     self.chunk_ids[i] if self.chunk_ids else None)

    def set_tags(self, i: int, tags: list[str]):
        self.tags[i] = tags
        self._set_chunk_field(i, "tags", tags)

    def set_summary(self, i: int, summary: str):
        self.summaries[i] = summary
        self._set_chunk_field(i, "summary", summary)

    def begin(self):
        """Start measuring pace; after a resume only this run's work counts toward the ETA."""
        self._pace_start = (time.monotonic(), self.done)

    def to_dict(self) -> dict:
        eta = None
        if self._pace_start and self.done < self.total:
            started, done_before = self._pace_start
            if self.done > done_before:
                eta = round((time.monotonic() - started) / (self.done - done_before) * (self.total - self.done))
        percent = round(100 * self.done / self.total) if self.total else None
        # Pausing until the worker reaches its next checkpoint, then paused
        stopped = self.paused and not (self.worker and self.worker.is_alive())
        status = "Paused" if stopped else "Pausing..." if self.paused else self.stage
        if self.paused:
            eta_text = ""
        elif eta is None:
            eta_text = "" if percent else "Estimating time..."
        else:
            eta_text = f"~{max(eta, 1)}s left" if eta < 60 else f"~{round(eta / 60)} min left"
        return {
            "id": self.id,
            "filename": self.filename,
            "source": self.source,
            "percent": percent,
            "status_text": status if percent is None else f"{status} · {percent}%",
            "eta_text": eta_text,
            "error": self.error,
            "paused": self.paused,
            "stopped": stopped,
        }


def create(filename: str, source: str, source_id: str, content: bytes, content_type: Optional[str],
           file_hash: str) -> Optional[UploadJob]:
    """Register an upload as an 'uploading' document, replacing a saved one of that name.

    Returns None if a document of that name is already uploading.
    """
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO documents (filename, file_hash, source_id, status, content)
               VALUES (%s, %s, %s, 'uploading', %s)
               ON CONFLICT (filename) DO UPDATE SET
                   file_hash = EXCLUDED.file_hash, source_id = EXCLUDED.source_id, session_id = NULL,
                   metadata = NULL, status = 'uploading', content = EXCLUDED.content
               WHERE documents.status = 'ready'
               RETURNING id""",
            (filename, file_hash, source_id, content),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("DELETE FROM chunks WHERE doc_id = %s", (row[0],))
    job = UploadJob(filename, source, content, content_type, id=row[0], file_hash=file_hash)
    with _lock:
        _jobs[job.id] = job
    return job


def enqueue(job: UploadJob):
    """Put a job at the back of the queue; call before starting its worker so start order is queue order."""
    with _turn:
        _queue.append(job)
        if _queue[0] is not job:
            job.stage = "Queued"


def wait_turn(job: UploadJob):
    """Block until the job is first in the queue; raises Cancelled if it is cancelled or paused meanwhile."""
    with _turn:
        while _queue[0] is not job:
            job.check_cancelled()
            _turn.wait(timeout=0.5)  # also wakes to notice a pause or cancel, which don't notify
    if job.stage == "Queued":
        job.stage = "Extracting text"


def leave_queue(job: UploadJob):
    with _turn:
        if job in _queue:
            _queue.remove(job)
        _turn.notify_all()


def load_unfinished(source_names: dict[str, str]) -> list[UploadJob]:
    """Jobs a previous run left unfinished, with the results it saved, registered as running again.

    source_names maps a document's source_id to the job's source name. A document with no chunk rows was still
    extracting text and starts over from its stored file; complete chunks are kept, incomplete ones finished.
    """
    with db_cursor() as cur:
        cur.execute("""SELECT id, filename, file_hash, source_id, metadata, content FROM documents
                       WHERE status = 'uploading' ORDER BY id""")
        docs = cur.fetchall()
        cur.execute("""SELECT doc_id, chunk_id, chunk_text, metadata FROM chunks
                       WHERE doc_id IN (SELECT id FROM documents WHERE status = 'uploading') ORDER BY chunk_id""")
        chunk_rows: dict[int, list] = {}
        for doc_id, *row in cur.fetchall():
            chunk_rows.setdefault(doc_id, []).append(row)

    jobs = []
    for doc_id, filename, file_hash, source_id, doc_metadata, content in docs:
        # The upload's content type isn't stored; the browser derived it from the extension too
        job = UploadJob(filename, source_names[source_id], bytes(content or b""), mimetypes.guess_type(filename)[0],
                        id=doc_id, file_hash=file_hash, doc_metadata=doc_metadata)
        if doc_id in chunk_rows:
            rows = chunk_rows[doc_id]
            metas = [m or {} for _, _, m in rows]
            job.chunks = [{"text": text, **{k: v for k, v in m.items() if k not in ("tags", "summary")}}
                          for (_, text, _), m in zip(rows, metas)]
            job.chunk_ids = [chunk_id for chunk_id, _, _ in rows]
            job.tags, job.summaries = [m.get("tags") for m in metas], [m.get("summary") for m in metas]
        jobs.append(job)
    with _lock:
        _jobs.update((j.id, j) for j in jobs)
    return jobs


def _drop_unsaved(job_id: int):
    """Delete a job's document unless it was saved; its chunk rows go with it via ON DELETE CASCADE."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s AND status = 'uploading'", (job_id,))


def finish(job: UploadJob, error: Optional[str] = None):
    """Drop the job's unsaved rows; a failed job stays listed (in memory) for a while to show its error."""
    if job.id is not None:
        _drop_unsaved(job.id)
    with _lock:
        if error is None:
            _jobs.pop(job.id, None)
        else:
            job.error, job.failed_at = error, time.monotonic()


def get(job_id: int) -> Optional[UploadJob]:
    with _lock:
        return _jobs.get(job_id)


def cancel(job_id: int) -> bool:
    """Stop a job and delete its document and saved progress; its worker exits at its next checkpoint."""
    with _lock:
        job = _jobs.pop(job_id, None)
    if job is None:
        return False
    job.cancelled = True
    _drop_unsaved(job_id)
    return True


def list_jobs() -> list[dict]:
    now = time.monotonic()
    with _lock:
        for job_id in [i for i, j in _jobs.items() if j.failed_at and now - j.failed_at > FAILED_TTL_SECONDS]:
            del _jobs[job_id]
        return [j.to_dict() for j in _jobs.values()]
