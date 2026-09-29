from core.database import get_db_connection

def get_all_chunks():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM chunks ORDER BY id DESC")
            groups = cur.fetchall()
            
            result = []
            for chunk_id, chunk_name in groups:
                cur.execute("""
                    SELECT d.id, d.filename 
                    FROM documents d
                    JOIN chunk_documents cd ON d.id = cd.document_id
                    WHERE cd.chunk_id = %s
                """, (chunk_id,))
                docs = cur.fetchall()
                
                cur.execute("""
                    SELECT d.id, d.filename 
                    FROM documents d
                    WHERE d.id NOT IN (
                        SELECT document_id FROM chunk_documents WHERE chunk_id = %s
                    )
                """, (chunk_id,))
                unadded_docs = cur.fetchall()
                
                result.append({
                    "id": chunk_id, 
                    "name": chunk_name, 
                    "documents": [{"id": d[0], "filename": d[1]} for d in docs],
                    "unadded_documents": [{"id": d[0], "filename": d[1]} for d in unadded_docs]
                })
    return result

def create_chunk(name: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO chunks (name) VALUES (%s) RETURNING id", (name,))
            new_id = cur.fetchone()[0]
            conn.commit()
    return new_id

def delete_chunk(chunk_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE id = %s RETURNING id", (chunk_id,))
            deleted = cur.fetchone()
            conn.commit()
    return bool(deleted)

def add_document_to_chunk(chunk_id: int, document_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM documents WHERE id = %s", (document_id,))
            if not cur.fetchone():
                return False
                
            cur.execute("INSERT INTO chunk_documents (chunk_id, document_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (chunk_id, document_id))
            conn.commit()
    return True

def remove_document_from_chunk(chunk_id: int, document_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunk_documents WHERE chunk_id = %s AND document_id = %s RETURNING chunk_id", (chunk_id, document_id))
            deleted = cur.fetchone()
            conn.commit()
    return bool(deleted)
