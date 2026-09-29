import psycopg2
from core.config import settings

def migrate():
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    try:
        # Drop old chunks table which was for 5-line splits
        cur.execute("DROP TABLE IF EXISTS chunks CASCADE")
        
        # If file_groups exists, rename it to chunks, else create chunks
        cur.execute("SELECT to_regclass('public.file_groups')")
        has_file_groups = cur.fetchone()[0]
        
        if has_file_groups:
            cur.execute("ALTER TABLE file_groups RENAME TO chunks")
            cur.execute("ALTER TABLE file_group_documents RENAME TO chunk_documents")
            cur.execute("ALTER TABLE chunk_documents RENAME COLUMN group_id TO chunk_id")
        else:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS chunks (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS chunk_documents (
                    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
                    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                    PRIMARY KEY (chunk_id, document_id)
                )
            ''')
        
        conn.commit()
        print("Migration successful")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
