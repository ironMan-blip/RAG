from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import get_chat_completion

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        final_message = req.message
        if req.attached_filename:
            file_context = f"[Attached File: {req.attached_filename}]"
            final_message = f"{file_context}\n\n{final_message}" if final_message else file_context
            
        bot_reply = get_chat_completion(final_message)
        return ChatResponse(reply=bot_reply)
    except Exception as e:
        print(f"Error during AI request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
