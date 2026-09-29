from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.chunk_service import (
    get_all_chunks as fetch_all_chunks,
    create_chunk as make_chunk,
    delete_chunk as remove_chunk,
    add_document_to_chunk as add_doc_to_chunk,
    remove_document_from_chunk as remove_doc_from_chunk
)

router = APIRouter()

class ChunkCreate(BaseModel):
    name: str

class ChunkAddDocument(BaseModel):
    document_id: int

@router.get("/chunks")
async def get_all_chunks():
    try:
        return {"chunks": fetch_all_chunks()}
    except Exception as e:
        print(f"Error fetching chunks: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chunks")

@router.post("/chunks")
async def create_chunk(chunk: ChunkCreate):
    try:
        new_id = make_chunk(chunk.name)
        return {"id": new_id, "name": chunk.name, "documents": []}
    except Exception as e:
        print(f"Error creating chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chunk")

@router.delete("/chunks/{chunk_id}")
async def delete_chunk(chunk_id: int):
    try:
        success = remove_chunk(chunk_id)
        if success:
            return {"status": "success", "message": "Chunk deleted"}
        raise HTTPException(status_code=404, detail="Chunk not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chunk")

@router.post("/chunks/{chunk_id}/documents")
async def add_document_to_chunk(chunk_id: int, payload: ChunkAddDocument):
    try:
        success = add_doc_to_chunk(chunk_id, payload.document_id)
        if success:
            return {"status": "success", "message": "Document added to chunk"}
        raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding document to chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to add document to chunk")

@router.delete("/chunks/{chunk_id}/documents/{document_id}")
async def remove_document_from_chunk(chunk_id: int, document_id: int):
    try:
        success = remove_doc_from_chunk(chunk_id, document_id)
        if success:
            return {"status": "success", "message": "Document removed from chunk"}
        raise HTTPException(status_code=404, detail="Document not found in chunk")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error removing document from chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove document from chunk")
