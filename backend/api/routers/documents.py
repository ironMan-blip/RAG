from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from services.document_service import (
    process_and_save_document,
    get_all_documents as fetch_all_documents,
    delete_document as remove_doc
)

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), source: str = Form('library')):
    uuid_map = {
        'library': '79279d88-e2c3-4a36-9da6-3f02dd71796b',
        'tools': 'b8118424-5418-47b7-a661-8bb768aa8ef5',
        'chat': '20a26963-d20c-469f-8837-620321d589a6'
    }
    actual_source_id = uuid_map.get(source, source)
    try:
        content = await file.read()
        upload_message, extracted_text = await run_in_threadpool(
            process_and_save_document, 
            file.filename, 
            content, 
            file.content_type, 
            actual_source_id
        )
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
