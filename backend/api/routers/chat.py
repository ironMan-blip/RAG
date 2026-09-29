from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import get_chat_completion

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        bot_reply = get_chat_completion(req.message)
        return ChatResponse(reply=bot_reply)
    except Exception as e:
        print(f"Error during AI request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
