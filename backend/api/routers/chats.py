import uuid

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from models.schemas import NewChatResponse
from services.history_service import GREETING, delete_chat_by_id, get_all_chats, get_full_chat_history

router = APIRouter()


@router.post("/chats", response_model=NewChatResponse)
async def new_chat_endpoint():
    # Nothing is stored until the first message; the chat row is created with it
    return NewChatResponse(session_id=str(uuid.uuid4()), history=[GREETING])


@router.get("/chats")
async def get_chats_endpoint():
    return {"chats": await run_in_threadpool(get_all_chats)}


@router.get("/chats/{session_id}")
async def get_chat_history_endpoint(session_id: str):
    return {"history": await run_in_threadpool(get_full_chat_history, session_id)}


@router.delete("/chats/{session_id}")
async def delete_chat_endpoint(session_id: str):
    await run_in_threadpool(delete_chat_by_id, session_id)
    return {"status": "success"}
