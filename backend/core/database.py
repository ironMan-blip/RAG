import psycopg2
from core.config import settings

def get_db_connection():
    """Provides a database connection."""
    return psycopg2.connect(settings.DATABASE_URL)
