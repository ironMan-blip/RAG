from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import get_chat_completion
from services.history_service import get_all_chats, get_full_chat_history, delete_chat_by_id

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        final_message = req.message
        bot_reply = get_chat_completion(final_message, attached_filename=req.attached_filename, model=req.model, session_id=req.session_id)
        return ChatResponse(reply=bot_reply)
    except Exception as e:
        print(f"Error during AI request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/models")
async def get_models():
    from core.config import settings
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
        chats = get_all_chats()
        return {"chats": chats}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/chats/{session_id}")
async def get_chat_history_endpoint(session_id: str):
    try:
        history = get_full_chat_history(session_id)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/chats/{session_id}")
async def delete_chat_endpoint(session_id: str):
    try:
        success = delete_chat_by_id(session_id)
        if success:
            return {"status": "success"}
        raise HTTPException(status_code=500, detail="Failed to delete chat")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
