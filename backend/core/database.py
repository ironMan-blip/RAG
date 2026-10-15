import logging
from contextlib import contextmanager

from psycopg2.pool import ThreadedConnectionPool

from core.config import settings

logger = logging.getLogger(__name__)

pool = None
try:
    pool = ThreadedConnectionPool(1, 20, settings.DATABASE_URL)
except Exception:
    logger.exception("Error creating connection pool")


@contextmanager
def db_cursor():
    """Yield a pooled cursor in one transaction: commit on success, roll back on error."""
    if pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    conn = pool.getconn()
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        pool.putconn(conn)
