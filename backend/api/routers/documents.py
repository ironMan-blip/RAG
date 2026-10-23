from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from services import chunk_service, document_service

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), source: str = Form('library')):
    source_id = document_service.SOURCE_IDS.get(source)
    if source_id is None:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
    upload_message = await run_in_threadpool(
        document_service.process_and_save_document, file.filename, await file.read(), file.content_type, source_id
    )
    return {"filename": file.filename, "status": "success", "message": upload_message}


@router.get("/upload-sources")
async def get_upload_sources():
    return {"sources": document_service.get_upload_sources()}


@router.get("/documents")
async def get_all_documents(q: str = ""):
    return {"documents": await run_in_threadpool(document_service.get_all_documents, q)}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    if not await run_in_threadpool(document_service.delete_document, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "success", "message": "Document deleted"}


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(doc_id: int):
    return {"chunks": await run_in_threadpool(chunk_service.get_document_chunks, doc_id)}


@router.post("/chunks/{chunk_id}/tags")
async def regenerate_chunk_tags(chunk_id: int):
    try:
        metadata_text = await run_in_threadpool(chunk_service.regenerate_chunk_metadata, chunk_id)
    except chunk_service.GenerationFailed:
        raise HTTPException(status_code=502, detail="Tag generation failed")
    if metadata_text is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {"chunk_id": chunk_id, "metadata_text": metadata_text}


@router.post("/chunks/{chunk_id}/previous-summary")
async def regenerate_previous_summary(chunk_id: int):
    try:
        previous_summary_text = await run_in_threadpool(chunk_service.regenerate_previous_summary, chunk_id)
    except chunk_service.GenerationFailed:
        raise HTTPException(status_code=502, detail="Summary generation failed")
    if previous_summary_text is None:
        raise HTTPException(status_code=404, detail="Chunk not found or has no previous chunk")
    return {"chunk_id": chunk_id, "previous_summary_text": previous_summary_text}
