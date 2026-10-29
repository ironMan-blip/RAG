import uuid

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from core.config import settings
from models.schemas import ChatResponse
from services.document_service import SOURCE_IDS, process_and_save_document
from core.timing import timed
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
    timings = []
    if file and file.filename:
        attached_filename = file.filename
        with timed(timings, "file"):
            await run_in_threadpool(
                process_and_save_document, file.filename, await file.read(), file.content_type, SOURCE_IDS['chat'], session_id
            )
        header = f"[Attached File: {file.filename}]"
        message = f"{header}\n\n{message}" if message.strip() else header

    bot_reply, prompt, timings = await run_in_threadpool(get_chat_completion, message, attached_filename, model, session_id, timings)
    return ChatResponse(
        session_id=session_id,
        messages=[{"sender": "user", "text": message}, {"sender": "bot", "text": bot_reply, "prompt": prompt, "timings": timings}]
    )


@router.get("/models")
async def get_models():
    def format_name(m):
        return m.split("/")[-1].replace("-", " ").title()

    models = [{"value": m, "label": format_name(m)} for m in settings.chat_models]
    return {"models": models, "default": models[0]["value"] if models else None}
