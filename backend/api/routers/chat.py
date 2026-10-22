import uuid

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from core.config import settings
from models.schemas import ChatResponse, NewChatResponse
from services.document_service import SOURCE_IDS, process_and_save_document
from services.history_service import GREETING, delete_chat_by_id, get_all_chats, get_full_chat_history
from services.llm_service import get_chat_completion

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    message: str = Form(""),
    model: str = Form(None),
    session_id: str = Form(None),
    file: UploadFile = File(None)
):
    if not session_id or session_id in ("null", "undefined"):
        session_id = str(uuid.uuid4())

    attached_filename = None
    if file and file.filename:
        attached_filename = file.filename
        await run_in_threadpool(
            process_and_save_document, file.filename, await file.read(), file.content_type, SOURCE_IDS['chat'], session_id
        )
        header = f"[Attached File: {file.filename}]"
        message = f"{header}\n\n{message}" if message.strip() else header

    bot_reply = await run_in_threadpool(get_chat_completion, message, attached_filename, model, session_id)
    return ChatResponse(
        session_id=session_id,
        messages=[{"sender": "user", "text": message}, {"sender": "bot", "text": bot_reply}]
    )


@router.get("/models")
async def get_models():
    def format_name(m):
        return m.split("/")[-1].replace(":free", "").replace("-", " ").title()

    models = [{"value": m, "label": format_name(m)} for m in settings.chat_models]
    return {"models": models, "default": models[0]["value"] if models else None}


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
