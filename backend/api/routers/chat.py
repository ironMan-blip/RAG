from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import get_chat_completion
from core.database import get_db_connection

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

@router.get("/chats")
async def get_chats():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, created_at FROM chats ORDER BY created_at DESC")
                rows = cur.fetchall()
                return {"chats": [{"id": row[0], "created_at": row[1]} for row in rows]}
    except Exception as e:
        print(f"Error getting chats: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/chats/{session_id}")
async def get_chat_history(session_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_message, bot_reply FROM chat_history WHERE session_id = %s ORDER BY created_at ASC", (session_id,))
                rows = cur.fetchall()
                history = []
                for row in rows:
                    history.append({"role": "user", "text": row[0]})
                    history.append({"role": "bot", "text": row[1]})
                return {"history": history}
    except Exception as e:
        print(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/chats/{session_id}")
async def delete_chat(session_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chats WHERE id = %s", (session_id,))
            conn.commit()
        return {"status": "success"}
    except Exception as e:
        print(f"Error deleting chat: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
