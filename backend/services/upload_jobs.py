import threading
import time
import uuid
from typing import Optional

from psycopg2.extras import Json

from core.database import db_cursor

# Failed jobs stay listed this long so the Library can show why; finished ones leave at once
FAILED_TTL_SECONDS = 600

# Jobs of this process: running, or failed and still listed. The upload_jobs table is the durable copy.
_jobs: dict[str, "UploadJob"] = {}
_lock = threading.Lock()

# Set on shutdown: a worker dying then is paused, not failed, so its row stays for resume
stopping = False

# Background jobs in upload order; only the first one is processed, the rest wait their turn
_queue: list["UploadJob"] = []
_turn = threading.Condition()


class Cancelled(Exception):
    """Raised in a worker whose job was cancelled or paused, to stop it at the next saved result."""


class UploadJob:
    """One document being processed and every result finished so far.

    A tracked job (has an id) mirrors each result to its upload_jobs row, so a restart resumes from there.
    An untracked job (chat attachments) only keeps them in memory.
    """

    def __init__(self, filename: str, source: str, content: bytes = b"", content_type: Optional[str] = None,
                 id: Optional[str] = None, chunks: Optional[list] = None, doc_metadata: Optional[dict] = None,
                 tags: Optional[list] = None, summaries: Optional[list] = None):
        self.id = id
        self.filename = filename
        self.source = source
        self.content = content
        self.content_type = content_type
        self.chunks = chunks  # None until extraction finishes
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
                cur.execute(f"UPDATE upload_jobs SET {sql} WHERE id = %s", (*params, self.id))

    def set_chunks(self, chunks: list[dict]):
        self.chunks, self.tags, self.summaries = chunks, [None] * len(chunks), [None] * len(chunks)
        self._update("chunks = %s, tags = %s, summaries = %s", Json(chunks), Json(self.tags), Json(self.summaries))

    def set_doc_metadata(self, metadata: dict):
        self.doc_metadata = metadata
        self._update("doc_metadata = %s", Json(metadata))

    def set_tags(self, i: int, tags: list[str]):
        self.tags[i] = tags
        self._update("tags = jsonb_set(tags, ARRAY[%s], %s)", str(i), Json(tags))

    def set_summary(self, i: int, summary: str):
        self.summaries[i] = summary
        self._update("summaries = jsonb_set(summaries, ARRAY[%s], %s)", str(i), Json(summary))

    def begin(self):
        """Start measuring pace; after a resume only this run's work counts toward the ETA."""
        self._pace_start = (time.monotonic(), self.done)

    def to_dict(self) -> dict:
        eta = None
        if self._pace_start and self.done < self.total:
            started, done_before = self._pace_start
            if self.done > done_before:
                eta = round((time.monotonic() - started) / (self.done - done_before) * (self.total - self.done))
        return {
            "id": self.id,
            "filename": self.filename,
            "source": self.source,
            "stage": self.stage,
            "percent": round(100 * self.done / self.total) if self.total else None,
            "eta_seconds": eta,
            "error": self.error,
            # Pausing until the worker reaches its next checkpoint, then paused
            "paused": self.paused,
            "stopped": self.paused and not (self.worker and self.worker.is_alive()),
        }


def create(filename: str, source: str, content: bytes, content_type: Optional[str]) -> UploadJob:
    job = UploadJob(filename, source, content, content_type, id=uuid.uuid4().hex)
    with db_cursor() as cur:
        cur.execute("INSERT INTO upload_jobs (id, filename, source, content, content_type) VALUES (%s, %s, %s, %s, %s)",
                    (job.id, filename, source, content, content_type))
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


def load_unfinished() -> list[UploadJob]:
    """Jobs a previous run left unfinished, with the results it saved, registered as running again."""
    with db_cursor() as cur:
        cur.execute("""SELECT id, filename, source, content, content_type, chunks, doc_metadata, tags, summaries
                       FROM upload_jobs ORDER BY created_at""")
        jobs = [UploadJob(filename, source, bytes(content), content_type, id=job_id, chunks=chunks,
                          doc_metadata=doc_metadata, tags=tags, summaries=summaries)
                for job_id, filename, source, content, content_type, chunks, doc_metadata, tags, summaries
                in cur.fetchall()]
    with _lock:
        _jobs.update((j.id, j) for j in jobs)
    return jobs


def finish(job: UploadJob, error: Optional[str] = None):
    """Drop the job's row; a failed job stays listed (in memory) for a while to show its error."""
    if job.id is not None:
        with db_cursor() as cur:
            cur.execute("DELETE FROM upload_jobs WHERE id = %s", (job.id,))
    with _lock:
        if error is None:
            _jobs.pop(job.id, None)
        else:
            job.error, job.failed_at = error, time.monotonic()


def get(job_id: str) -> Optional[UploadJob]:
    with _lock:
        return _jobs.get(job_id)


def cancel(job_id: str) -> bool:
    """Stop a job and delete its row and saved progress; its worker exits at its next checkpoint."""
    with _lock:
        job = _jobs.pop(job_id, None)
    if job is None:
        return False
    job.cancelled = True
    with db_cursor() as cur:
        cur.execute("DELETE FROM upload_jobs WHERE id = %s", (job_id,))
    return True


def list_jobs() -> list[dict]:
    now = time.monotonic()
    with _lock:
        for job_id in [i for i, j in _jobs.items() if j.failed_at and now - j.failed_at > FAILED_TTL_SECONDS]:
            del _jobs[job_id]
        return [j.to_dict() for j in _jobs.values()]
