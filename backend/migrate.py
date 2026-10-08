import psycopg2
from core.config import settings

def migrate():
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE documents ADD COLUMN session_id VARCHAR(255);")
        conn.commit()
        print("Column session_id added successfully.")
    except Exception as e:
        print("Migration error session_id (maybe already exists):", e)
        conn.rollback()
        
    try:
        cur.execute("ALTER TABLE documents ADD COLUMN metadata JSONB;")
        conn.commit()
        print("Column metadata added successfully.")
    except Exception as e:
        print("Migration error metadata (maybe already exists):", e)
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
