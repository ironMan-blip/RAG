from openai import OpenAI
from core.config import settings
import os
import io

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from core.database import get_db_connection

def get_database_context() -> str:
    context = ""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT filename, content FROM documents")
                rows = cur.fetchall()
                for filename, content in rows:
                    context += f"\n--- Content of {filename} ---\n{content}\n"
                    
                cur.execute("""
                    SELECT c.name, array_agg(d.filename)
                    FROM chunks c
                    LEFT JOIN chunk_documents cd ON c.id = cd.chunk_id
                    LEFT JOIN documents d ON cd.document_id = d.id
                    GROUP BY c.name
                """)
                group_rows = cur.fetchall()
                if group_rows:
                    context += "\n--- Chunks (Document Groups) ---\n"
                    for chunk_name, filenames in group_rows:
                        valid_files = [f for f in filenames if f is not None]
                        files_str = ", ".join(valid_files) if valid_files else "No files"
                        context += f"Chunk '{chunk_name}' contains files: {files_str}\n"
    except Exception as e:
        context = f"[Database error: {e}]"
        print(f"Error fetching database context: {e}")
        
    return context

# Initialize the OpenAI client pointing to OpenRouter
client = OpenAI(
  base_url=settings.OPENROUTER_BASE_URL,
  api_key=settings.OPENROUTER_API_KEY,
)

def get_chat_completion(message: str) -> str:
    """Sends a message to the AI and retrieves the reply, including database context."""
    db_context = get_database_context()
    
    system_prompt = "You are a very helpful AI assistant. Use the provided database context to answer the user's query."
    if db_context:
        system_prompt += f"\n\nDATABASE CONTEXT:\n{db_context}"

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": message
            }
        ],
        extra_body={"reasoning": {"enabled": True}}
    )
    
    return response.choices[0].message.content
