from core.database import get_db_connection
from typing import List, Tuple

def get_recent_chat_history(session_id: str, limit: int = 5) -> List[Tuple[str, str]]:
    if not session_id:
        return []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_message, bot_reply FROM chat_history WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
                    (session_id, limit)
                )
                rows = cur.fetchall()
                if rows:
                    rows.reverse()
                    return rows
    except Exception as e:
        print(f"Error fetching chat history: {e}")
    return []

def save_chat_history(session_id: str, message: str, bot_reply: str, model: str, chat_title: str = None):
    if not session_id:
        return
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM chats WHERE id = %s", (session_id,))
                if not cur.fetchone():
                    cur.execute("INSERT INTO chats (id, name) VALUES (%s, %s)", (session_id, chat_title or "New Chat"))
                    
                cur.execute(
                    "INSERT INTO chat_history (session_id, user_message, bot_reply, model) VALUES (%s, %s, %s, %s)",
                    (session_id, message, bot_reply, model)
                )
            conn.commit()
    except Exception as e:
        print(f"Error saving chat history: {e}")

def get_all_chats():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, created_at FROM chats ORDER BY created_at DESC")
                rows = cur.fetchall()
                return [{"id": row[0], "name": row[1], "created_at": row[2]} for row in rows]
    except Exception as e:
        print(f"Error getting chats: {e}")
        return []

def get_full_chat_history(session_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_message, bot_reply FROM chat_history WHERE session_id = %s ORDER BY created_at ASC", (session_id,))
                rows = cur.fetchall()
                history = []
                for row in rows:
                    history.append({"role": "user", "text": row[0]})
                    history.append({"role": "bot", "text": row[1]})
                return history
    except Exception as e:
        print(f"Error getting full chat history: {e}")
        return []

def delete_chat_by_id(session_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chats WHERE id = %s", (session_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return False
