import os
import hashlib
import psycopg2
from core.config import settings
from init_db import extract_text_from_file

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")

def sync_uploads():
    print(f"Syncing {UPLOAD_DIR} to database...")
    if not os.path.exists(UPLOAD_DIR):
        print("No uploads directory found.")
        return

    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()

    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.isfile(file_path):
            continue

        print(f"Processing {filename}...")
        content = extract_text_from_file(file_path, filename)
        
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        file_url = f"local://{file_path}"
        
        try:
            cur.execute(
                "INSERT INTO documents (filename, content, file_hash, file_url) VALUES (%s, %s, %s, %s) ON CONFLICT (filename) DO UPDATE SET content = EXCLUDED.content, file_hash = EXCLUDED.file_hash, file_url = EXCLUDED.file_url RETURNING id",
                (filename, content, file_hash, file_url)
            )
            result = cur.fetchone()
            if result:
                doc_id = result[0]
            else:
                cur.execute("SELECT id FROM documents WHERE filename = %s", (filename,))
                doc_id = cur.fetchone()[0]
            
            cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
            
            lines = content.split('\n')
            chunk_lines = []
            for line in lines:
                chunk_lines.append(line)
                if len(chunk_lines) == 5:
                    cur.execute(
                        "INSERT INTO chunks (document_id, chunk_text) VALUES (%s, %s)",
                        (doc_id, '\n'.join(chunk_lines))
                    )
                    chunk_lines = []
            if chunk_lines:
                cur.execute(
                    "INSERT INTO chunks (document_id, chunk_text) VALUES (%s, %s)",
                    (doc_id, '\n'.join(chunk_lines))
                )
                
            print(f"Synced {filename}")
        except Exception as e:
            print(f"Failed to sync {filename}: {e}")
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()
    print("Sync complete.")

if __name__ == "__main__":
    sync_uploads()
