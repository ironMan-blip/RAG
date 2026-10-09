from openai import OpenAI
from langsmith import traceable, wrappers
from core.config import settings
from core.database import get_db_connection
from core.ml import embedder
from services.history_service import get_recent_chat_history, save_chat_history
from services.document_service import get_all_documents
import httpx

client = wrappers.wrap_openai(OpenAI(
  base_url=settings.OPENROUTER_BASE_URL,
  api_key=settings.OPENROUTER_API_KEY,
))

def get_document_names_str(session_id: str = None) -> str:
    docs = get_all_documents(session_id)
    if not docs:
        return "None"
    return "\n".join([f"{i+1}. {doc['filename']}" for i, doc in enumerate(docs)])

@traceable
def get_database_context(query: str, attached_filename: str = None, session_id: str = None) -> str:
    if embedder is None:
        print("Error: Embedder is None in get_database_context")
        return ""
    context = ""
    try:
        query_embedding = embedder.encode(query).tolist()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if attached_filename:
                    cur.execute("""
                        SELECT sub.chunk_text, sub.filename, sub.chunk_id FROM (
                            SELECT c.chunk_text, d.filename, c.chunk_id
                            FROM chunks c
                            JOIN documents d ON c.doc_id = d.id
                            WHERE d.filename = %s
                            ORDER BY c.chunk_embedding <-> %s::vector
                            LIMIT 3
                        ) sub
                        ORDER BY sub.chunk_id ASC
                    """, (attached_filename, str(query_embedding)))
                else:
                    cur.execute("""
                        SELECT c.chunk_text, d.filename 
                        FROM chunks c
                        JOIN documents d ON c.doc_id = d.id
                        WHERE d.session_id IS NULL OR d.session_id = %s
                        ORDER BY c.chunk_embedding <-> %s::vector
                        LIMIT 5
                    """, (session_id, str(query_embedding)))
                
                rows = cur.fetchall()
                if rows:
                    context += "Relevant excerpts from knowledge base:\n"
                    for i, row in enumerate(rows):
                        context += f"\n--- Excerpt {i+1} (from {row[1]}) ---\n{row[0]}\n"
    except Exception as e:
        context = f"[Database error: {e}]"
        print(f"Error fetching database context: {e}")
    return context

@traceable
def jev_decide_if_context_needed(message: str, session_id: str = None) -> bool:
    """Uses Jev to decide if external documents are needed for this query."""
    doc_names = get_document_names_str(session_id)
    
    chat_history_str = "None"
    if session_id:
        history = get_recent_chat_history(session_id, limit=3)
        if history:
            chat_history_str = "\n".join([f"User: {h[0]}\nBot: {h[1]}" for h in history])

    payload = {
        "model": "typesafe/jev-1.13",
        "state": {
            "request": message, 
            "available_documents": doc_names,
            "chat_history": chat_history_str
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
    
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = httpx.post("https://openrouter.ai/api/alpha/decisions", headers=headers, json=payload, timeout=10.0)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            print(f"Jev API returned an error payload: {result['error']}")
            return True
        probability_yes = result.get("answers", {}).get("needs_context", {}).get("noul", 0.0)
        return probability_yes > 0.5
    except Exception as e:
        print(f"Error calling jev: {e}")
        return True

def generate_chat_title(message: str) -> str:
    try:
        title_response = client.chat.completions.create(
            model=settings.LLM_MODEL1,
            messages=[{"role": "user", "content": f"Summarize this prompt in 3-5 words for a chat title. Output only the title, no quotes or other text:\n{message}"}],
        )
        return title_response.choices[0].message.content.strip().strip('"')
    except Exception:
        return message[:30] + "..." if len(message) > 30 else message

def generate_tags_for_chunk(chunk_text: str) -> str:
    try:
        prompt = f"Given the following text chunk, generate a JSON object containing descriptive tags and metadata. Output ONLY valid JSON, no markdown blocks. Example: {{\"tags\": [\"tag1\", \"tag2\"]}}\n\nText:\n{chunk_text}"
        response = client.chat.completions.create(
            model=settings.LLM_MODEL1,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        return content
    except Exception as e:
        print(f"Error generating tags for chunk: {e}")
        return "{}"

@traceable
def get_chat_completion(message: str, attached_filename: str = None, model: str = None, session_id: str = None) -> str:
    """Sends a message to the AI and retrieves the reply, including database context."""
    db_context = ""
    needs_context = True if attached_filename else jev_decide_if_context_needed(message, session_id)
    
    if needs_context:
        db_context = get_database_context(message, attached_filename, session_id)
    
    system_prompt = "You are a very helpful AI assistant."
    if db_context:
        system_prompt += f"\n\nYou have been provided with relevant document excerpts below. You MUST use them to answer the user's query. Even if the user asks you to summarize a file they attached or mentioned, DO NOT say you cannot see it. Assume the context below is the file they are referring to.\n\nDOCUMENT CONTEXT:\n{db_context}\n" 

    is_new_chat = True
    if session_id:
        history = get_recent_chat_history(session_id, limit=5)
        if history:
            is_new_chat = False
            system_prompt += "\n\n <chat_history>\n PREVIOUS CHAT HISTORY (Last 5 messages):\n"
            for row in history:
                system_prompt += f"\nUser: {row[0]}\nAI: {row[1]}\n"
            system_prompt += "\n </chat_history>\n"

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
        import threading
        def save_history_bg():
            chat_title = generate_chat_title(message) if is_new_chat else None
            save_chat_history(session_id, message, bot_reply, used_model, chat_title)
        threading.Thread(target=save_history_bg).start()

    return bot_reply
