from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from services.document_service import (
    process_and_save_document,
    get_all_documents as fetch_all_documents,
    delete_document as remove_doc
)

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        upload_message, extracted_text = await run_in_threadpool(process_and_save_document, file.filename, content, file.content_type)
        return {"filename": file.filename, "status": "success", "message": upload_message, "extracted_text": extracted_text}
    except Exception as e:
        print(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

@router.get("/documents")
async def get_all_documents():
    try:
        docs = await run_in_threadpool(fetch_all_documents)
        return {"documents": docs}
    except Exception as e:
        print(f"Failed to fetch documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch documents")

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    try:
        success = await run_in_threadpool(remove_doc, doc_id)
        if success:
            return {"status": "success", "message": "Document deleted"}
        raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")
