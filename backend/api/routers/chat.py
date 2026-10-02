import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from core.config import settings
from models.schemas import ChatResponse
from services.llm_service import get_chat_completion
from services.history_service import get_all_chats, get_full_chat_history, delete_chat_by_id
from services.document_service import process_and_save_document

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    message: str = Form(""),
    model: str = Form(None),
    session_id: str = Form(None),
    file: UploadFile = File(None)
):
    try:
        attached_filename = None
        final_message = message
        
        if file and file.filename:
            content = await file.read()
            upload_message, extracted_text = await run_in_threadpool(process_and_save_document, file.filename, content, file.content_type)
            attached_filename = file.filename
            
            # Format message with file context logic moved to backend
            if message.strip():
                final_message = f"[Attached File: {file.filename}]\n\n{message}"
            else:
                final_message = f"[Attached File: {file.filename}]"
        
        if not session_id or session_id == "null" or session_id == "undefined":
            session_id = str(uuid.uuid4())
            
        bot_reply = await run_in_threadpool(get_chat_completion, final_message, attached_filename, model, session_id)
        return ChatResponse(reply=bot_reply, session_id=session_id)
    except Exception as e:
        print(f"Error during AI request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/models")
async def get_models():
    def format_name(m):
        if not m: return "Unknown"
        name = m.split("/")[-1].replace(":free", "")
        return name.replace("-", " ").title()
        
    models = []
    if settings.LLM_MODEL1:
        models.append({"value": settings.LLM_MODEL1, "label": format_name(settings.LLM_MODEL1)})
    if settings.LLM_MODEL2:
        models.append({"value": settings.LLM_MODEL2, "label": format_name(settings.LLM_MODEL2)})
    if settings.LLM_MODEL3:
        models.append({"value": settings.LLM_MODEL3, "label": format_name(settings.LLM_MODEL3)})
        
    return {"models": models}

@router.get("/chats")
async def get_chats_endpoint():
    try:
        chats = await run_in_threadpool(get_all_chats)
        return {"chats": chats}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/chats/{session_id}")
async def get_chat_history_endpoint(session_id: str):
    try:
        history = await run_in_threadpool(get_full_chat_history, session_id)
        return {"history": history}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/chats/{session_id}")
async def delete_chat_endpoint(session_id: str):
    try:
        success = await run_in_threadpool(delete_chat_by_id, session_id)
        if success:
            return {"status": "success"}
        raise HTTPException(status_code=500, detail="Failed to delete chat")
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")
