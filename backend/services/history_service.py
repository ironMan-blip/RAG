import logging

from psycopg2.extras import Json

from core.database import db_cursor

logger = logging.getLogger(__name__)

GREETING = {"sender": "bot", "text": "Hello! I'm your AI assistant. How can I help you today?"}


def get_recent_chat_history(session_id: str, limit: int = 5) -> list[tuple[str, str]]:
    """Last `limit` (user, bot) turns, oldest first. Best-effort: [] on DB error."""
    if not session_id:
        return []
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT user_message, bot_reply FROM chat_history WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
                (session_id, limit)
            )
            return cur.fetchall()[::-1]
    except Exception:
        logger.exception("Error fetching chat history")
        return []


def save_chat_history(session_id: str, message: str, bot_reply: str, model: str, prompt: str, timings: list, chat_title: str = None):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO chats (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (session_id, chat_title or "New Chat")
        )
        cur.execute(
            "INSERT INTO chat_history (session_id, user_message, bot_reply, model, prompt, timings) VALUES (%s, %s, %s, %s, %s, %s)",
            (session_id, message, bot_reply, model, prompt, Json(timings))
        )


def get_all_chats():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, created_at FROM chats ORDER BY created_at DESC")
        return [{"id": id, "name": name or "New Chat", "created_at": created_at} for id, name, created_at in cur.fetchall()]


def get_full_chat_history(session_id: str):
    with db_cursor() as cur:
        cur.execute("SELECT user_message, bot_reply, prompt, timings FROM chat_history WHERE session_id = %s ORDER BY created_at ASC", (session_id,))
        rows = cur.fetchall()
    history = [GREETING]
    for user_message, bot_reply, prompt, timings in rows:
        history.append({"sender": "user", "text": user_message})
        history.append({"sender": "bot", "text": bot_reply, "prompt": prompt, "timings": timings})
    return history


def delete_chat_by_id(session_id: str):
    # chat_history rows go with it via ON DELETE CASCADE
    with db_cursor() as cur:
        cur.execute("DELETE FROM chats WHERE id = %s", (session_id,))
