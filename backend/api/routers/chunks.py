from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.database import get_db_connection

router = APIRouter()

class ChunkCreate(BaseModel):
    name: str

class ChunkAddDocument(BaseModel):
    document_id: int

@router.get("/chunks")
async def get_all_chunks():
    try:
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
        return {"chunks": result}
    except Exception as e:
        print(f"Error fetching chunks: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chunks")

@router.post("/chunks")
async def create_chunk(chunk: ChunkCreate):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO chunks (name) VALUES (%s) RETURNING id", (chunk.name,))
                new_id = cur.fetchone()[0]
                conn.commit()
        return {"id": new_id, "name": chunk.name, "documents": []}
    except Exception as e:
        print(f"Error creating chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chunk")

@router.delete("/chunks/{chunk_id}")
async def delete_chunk(chunk_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE id = %s RETURNING id", (chunk_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Chunk not found")
                conn.commit()
        return {"status": "success", "message": "Chunk deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chunk")

@router.post("/chunks/{chunk_id}/documents")
async def add_document_to_chunk(chunk_id: int, payload: ChunkAddDocument):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM documents WHERE id = %s", (payload.document_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Document not found")
                    
                cur.execute("INSERT INTO chunk_documents (chunk_id, document_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (chunk_id, payload.document_id))
                conn.commit()
        return {"status": "success", "message": "Document added to chunk"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding document to chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to add document to chunk")

@router.delete("/chunks/{chunk_id}/documents/{document_id}")
async def remove_document_from_chunk(chunk_id: int, document_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunk_documents WHERE chunk_id = %s AND document_id = %s RETURNING chunk_id", (chunk_id, document_id))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Document not found in chunk")
                conn.commit()
        return {"status": "success", "message": "Document removed from chunk"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error removing document from chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove document from chunk")
