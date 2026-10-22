import logging
import threading

import httpx
from langsmith import traceable, wrappers
from openai import OpenAI

from core.config import settings
from core.database import db_cursor
from core.ml import embedder
from services.document_service import get_document_names
from services.history_service import get_recent_chat_history, save_chat_history

logger = logging.getLogger(__name__)

client = wrappers.wrap_openai(OpenAI(
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY,
))
_http = httpx.Client(timeout=10.0, headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"})

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
SYSTEM_PROMPT = "You are a very helpful AI assistant."
CONTEXT_PROMPT = (
    "\n\nYou have been provided with relevant document excerpts below. You MUST use them to answer the user's query. "
    "Even if the user asks you to summarize a file they attached or mentioned, DO NOT say you cannot see it. "
    "Assume the context below is the file they are referring to.\n\nDOCUMENT CONTEXT:\n{context}\n"
)


@traceable
def get_database_context(query: str, attached_filename: str = None, session_id: str = None) -> str:
    """Nearest chunks to the query: from the attached file if any, else from all visible documents."""
    query_embedding = str(embedder.encode(query).tolist())
    try:
        with db_cursor() as cur:
            if attached_filename:
                cur.execute("""
                    SELECT sub.chunk_text, sub.filename, sub.previous_summary FROM (
                        SELECT c.chunk_text, d.filename, c.chunk_id, c.previous_summary
                        FROM chunks c
                        JOIN documents d ON c.doc_id = d.id
                        WHERE d.filename = %s
                        ORDER BY c.chunk_embedding <-> %s::vector
                        LIMIT 3
                    ) sub
                    ORDER BY sub.chunk_id ASC
                """, (attached_filename, query_embedding))
            else:
                cur.execute("""
                    SELECT c.chunk_text, d.filename, c.previous_summary
                    FROM chunks c
                    JOIN documents d ON c.doc_id = d.id
                    WHERE d.session_id IS NULL OR d.session_id = %s
                    ORDER BY c.chunk_embedding <-> %s::vector
                    LIMIT 5
                """, (session_id, query_embedding))
            rows = cur.fetchall()
    except Exception:
        logger.exception("Error fetching database context")
        return ""
    if not rows:
        return ""
    excerpts = "".join(
        f"\n--- Excerpt {i} (from {filename}) ---\n"
        + (f"[Summary of preceding text: {summary}]\n" if summary else "")
        + f"{text}\n"
        for i, (text, filename, summary) in enumerate(rows, 1)
    )
    return "Relevant excerpts from knowledge base:\n" + excerpts


@traceable
def jev_decide_if_context_needed(message: str, history: list[tuple[str, str]], session_id: str = None) -> bool:
    """Uses Jev to decide if external documents are needed for this query. Defaults to True on failure."""
    try:
        doc_names = get_document_names(session_id)
        payload = {
            "model": "typesafe/jev-1.13",
            "state": {
                "request": message,
                "available_documents": "\n".join(f"{i}. {name}" for i, name in enumerate(doc_names, 1)) or "None",
                "chat_history": "\n".join(f"User: {u}\nBot: {b}" for u, b in history) or "None",
            },
            "questions": {
                "needs_context": {
                    "type": "noul",
                    "instructions": "Does `request` require looking up facts, data, or external documents? The following documents are available in the database: `available_documents`. Consider the recent chat context: `chat_history`.",
                    "criteria": {
                        "false": "casual greetings, conversational chat, or statements that require no context",
                        "true": "factual queries or questions that need external documents"
                    }
                }
            }
        }
        response = _http.post(JEV_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            logger.warning("Jev API returned an error payload: %s", result["error"])
            return True
        return result.get("answers", {}).get("needs_context", {}).get("noul", 0.0) > 0.5
    except Exception:
        logger.exception("Error calling jev")
        return True


def generate_chat_title(message: str) -> str:
    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL1,
            messages=[{"role": "user", "content": f"Summarize this prompt in 3-5 words for a chat title. Output only the title, no quotes or other text:\n{message}"}],
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception:
        return message[:30] + "..." if len(message) > 30 else message


def _save_turn(session_id: str, message: str, bot_reply: str, model: str, is_new_chat: bool):
    try:
        title = generate_chat_title(message) if is_new_chat else None
        save_chat_history(session_id, message, bot_reply, model, title)
    except Exception:
        logger.exception("Error saving chat history")


@traceable
def get_chat_completion(message: str, attached_filename: str = None, model: str = None, session_id: str = None) -> str:
    """Sends a message to the AI and retrieves the reply, including database context."""
    history = get_recent_chat_history(session_id, limit=5)

    system_prompt = SYSTEM_PROMPT
    if attached_filename or jev_decide_if_context_needed(message, history[-3:], session_id):
        db_context = get_database_context(message, attached_filename, session_id)
        if db_context:
            system_prompt += CONTEXT_PROMPT.format(context=db_context)

    if history:
        turns = "".join(f"\nUser: {u}\nAI: {b}\n" for u, b in history)
        system_prompt += f"\n\n <chat_history>\n PREVIOUS CHAT HISTORY (Last 5 messages):\n{turns}\n </chat_history>\n"

    used_model = model or settings.LLM_MODEL1
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        extra_body={"reasoning": {"enabled": True}}
    )

    if not response.choices:
        error_info = getattr(response, "error", "Unknown AI Provider Error")
        error_msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
        return f"⚠️ **AI Provider Error**: {error_msg}"

    bot_reply = response.choices[0].message.content

    if session_id:
        # Title generation is a second LLM call; keep it off the response path
        threading.Thread(target=_save_turn, args=(session_id, message, bot_reply, used_model, not history), daemon=True).start()

    return bot_reply
