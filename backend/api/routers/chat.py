from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import get_chat_completion

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
    # Generate nice names for the models
    def format_name(m):
        if not m: return "Unknown"
        # e.g., 'nvidia/nemotron-3-ultra-550b-a55b:free' -> 'nemotron-3-ultra-550b-a55b'
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
