import contextvars
import logging
import threading

from langsmith import traceable, wrappers
from openai import OpenAI

from core.config import settings
from core.timing import timed
from services.history_service import get_recent_chat_history, save_chat_history
from services.retrieval_service import decide_if_context_needed, get_database_context
from services.tagging_service import generate_chat_title

logger = logging.getLogger(__name__)

client = wrappers.wrap_openai(OpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key="ollama",  # Ollama ignores the key but the client requires one
))

SYSTEM_PROMPT = "You are a very helpful AI assistant."
CONTEXT_PROMPT = (
    "\n\nYou have been provided with relevant document excerpts below. You MUST use them to answer the user's query. "
    "Even if the user asks you to summarize a file they attached or mentioned, DO NOT say you cannot see it. "
    "Assume the context below is the file they are referring to.\n\nDOCUMENT CONTEXT:\n{context}\n"
)


def _save_turn(session_id: str, message: str, bot_reply: str, model: str, prompt: str, timings: list, is_new_chat: bool):
    try:
        title = generate_chat_title(message) if is_new_chat else None
        save_chat_history(session_id, message, bot_reply, model, prompt, timings, title)
    except Exception:
        logger.exception("Error saving chat history")


@traceable
def get_chat_completion(message: str, attached_filename: str = None, model: str = None, session_id: str = None, timings: list = None) -> tuple[str, str, list]:
    """Sends a message to the AI; returns (reply, the full prompt it received, per-step timings).
    `timings` may arrive pre-filled with steps the caller already ran (e.g. file processing)."""
    timings = timings if timings is not None else []
    with timed(timings, "history"):
        history = get_recent_chat_history(session_id, limit=5)

    system_prompt = SYSTEM_PROMPT
    if attached_filename:
        needs_context = True
    else:
        with timed(timings, "decide"):
            needs_context = decide_if_context_needed(message, history[-3:], session_id)
    if needs_context:
        db_context = get_database_context(message, attached_filename, session_id, timings)
        if db_context:
            system_prompt += CONTEXT_PROMPT.format(context=db_context)

    if history:
        turns = "".join(f"\nUser: {u}\nAI: {b}\n" for u, b in history)
        system_prompt += f"\n\n <chat_history>\n PREVIOUS CHAT HISTORY (Last 5 messages):\n{turns}\n </chat_history>\n"

    used_model = model or settings.LLM_MODEL1
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    with timed(timings, "llm"):
        response = client.chat.completions.create(model=used_model, messages=messages)
    bot_reply = response.choices[0].message.content
    prompt = "\n\n".join(f"[{m['role'].upper()}]\n{m['content']}" for m in messages)

    if session_id:
        # Title generation is a second LLM call; keep it off the response path
        # copy_context keeps the title call nested in this LangSmith trace
        threading.Thread(target=contextvars.copy_context().run, args=(_save_turn, session_id, message, bot_reply, used_model, prompt, timings, not history), daemon=True).start()

    return bot_reply, prompt, timings
