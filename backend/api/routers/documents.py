from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from services import chunk_service, document_service, upload_jobs

router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("/upload", status_code=202)
async def upload_file(file: UploadFile = File(...), source: str = Form('library')):
    if source not in document_service.SOURCE_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
    # Starlette spools the body to disk, so size is known before reading it into memory
    if file.size is None or file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than the 20 MB limit")
    return {"upload": document_service.start_upload(file.filename, await file.read(), file.content_type, source)}


@router.get("/uploads")
async def get_uploads():
    return {"uploads": upload_jobs.list_jobs()}


@router.delete("/uploads/{job_id}")
async def cancel_upload(job_id: str):
    if not await run_in_threadpool(upload_jobs.cancel, job_id):
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"status": "success", "message": "Upload cancelled"}


@router.post("/uploads/{job_id}/pause")
async def pause_upload(job_id: str):
    if not document_service.pause_upload(job_id):
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"status": "success", "message": "Upload pausing"}


@router.post("/uploads/{job_id}/resume")
async def resume_upload(job_id: str):
    error = document_service.resume_upload(job_id)
    if error:
        raise HTTPException(status_code=404 if error == "Upload not found" else 409, detail=error)
    return {"status": "success", "message": "Upload resumed"}


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
        chunk = await run_in_threadpool(chunk_service.regenerate_chunk_metadata, chunk_id)
    except chunk_service.GenerationFailed:
        raise HTTPException(status_code=502, detail="Tag generation failed")
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {"chunk": chunk}


@router.post("/chunks/{chunk_id}/previous-summary")
async def regenerate_previous_summary(chunk_id: int):
    try:
        chunk = await run_in_threadpool(chunk_service.regenerate_previous_summary, chunk_id)
    except chunk_service.GenerationFailed:
        raise HTTPException(status_code=502, detail="Summary generation failed")
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found or has no previous chunk")
    return {"chunk": chunk}
