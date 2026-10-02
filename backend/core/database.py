from psycopg2.pool import ThreadedConnectionPool
from core.config import settings

pool = None
try:
    pool = ThreadedConnectionPool(1, 20, settings.DATABASE_URL)
except Exception as e:
    print(f"Error creating connection pool: {e}")

class PooledConnection:
    def __init__(self, pool):
        if not pool:
            raise Exception("Database connection pool is not initialized.")
        self.pool = pool
        self.conn = self.pool.getconn()

    def __enter__(self):
        self.conn.__enter__()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.__exit__(exc_type, exc_val, exc_tb)
        self.pool.putconn(self.conn)

def get_db_connection():
    """Provides a database connection from the pool."""
    return PooledConnection(pool)
