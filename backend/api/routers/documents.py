from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from services import chunk_service, document_service

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), source: str = Form('library')):
    source_id = document_service.SOURCE_IDS.get(source, source)
    upload_message, extracted_text = await run_in_threadpool(
        document_service.process_and_save_document, file.filename, await file.read(), file.content_type, source_id
    )
    return {"filename": file.filename, "status": "success", "message": upload_message, "extracted_text": extracted_text}


@router.get("/documents")
async def get_all_documents():
    return {"documents": await run_in_threadpool(document_service.get_all_documents)}


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
    except chunk_service.TaggingFailed:
        raise HTTPException(status_code=502, detail="Tag generation failed")
    if metadata_text is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {"chunk_id": chunk_id, "metadata_text": metadata_text}
