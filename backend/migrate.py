import psycopg2
from core.config import settings

def migrate():
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE documents ADD COLUMN session_id VARCHAR(255);")
        conn.commit()
        print("Column added successfully.")
    except Exception as e:
        print("Migration error (maybe already exists):", e)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
