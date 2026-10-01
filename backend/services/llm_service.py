from openai import OpenAI
from langsmith import traceable, wrappers
from core.config import settings
from core.database import get_db_connection

from core.ml import embedder

try:
    from laya import Router
    laya_router = Router()
except ImportError:
    laya_router = None
    print("laya not installed. Run `pip install laya`")

@traceable
def get_database_context(query: str, attached_filename: str = None) -> str:
    context = ""
    try:
        if embedder is None:
            return ""
            
        query_embedding = embedder.encode(query).tolist()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if attached_filename:
                    # If a file is attached, prioritize returning its chunks.
                    # We'll get the first 3 chunks to help with summaries, plus 3 semantically relevant ones.
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
                    """, (attached_filename, query_embedding))
                else:
                    # General vector search across all documents
                    cur.execute("""
                        SELECT c.chunk_text, d.filename 
                        FROM chunks c
                        JOIN documents d ON c.doc_id = d.id
                        ORDER BY c.chunk_embedding <-> %s::vector
                        LIMIT 5
                    """, (query_embedding,))
                
                rows = cur.fetchall()
                if rows:
                    context += "Relevant excerpts from knowledge base:\n"
                    # rows may have 2 or 3 elements depending on the query used above, but chunk_text and filename are the first two
                    for i, row in enumerate(rows):
                        chunk_text, filename = row[0], row[1]
                        context += f"\n--- Excerpt {i+1} (from {filename}) ---\n{chunk_text}\n"
                        
    except Exception as e:
        context = f"[Database error: {e}]"
        print(f"Error fetching database context: {e}")
        
    return context

# Initialize the OpenAI client pointing to OpenRouter
client = wrappers.wrap_openai(OpenAI(
  base_url=settings.OPENROUTER_BASE_URL,
  api_key=settings.OPENROUTER_API_KEY,
))

@traceable
def laya_decide_if_context_needed(message: str) -> bool:
    """Uses Laya to decide if external documents are needed for this query."""
    if laya_router is None:
        return True

    questions = {
        "needs_context": {
            "type": "noul", 
            "instructions": "Does `request` require looking up facts, data, or external documents?",
            "criteria": {
                "false": "casual greetings, conversational chat, or statements that require no context",
                "true": "factual queries or questions that need external documents"
            }
        }
    }
    
    result = laya_router.predict({"request": message}, questions)
    probability_yes = result["answers"]["needs_context"]["noul"]
    print("probability_yes", probability_yes*100, "%")
    return probability_yes > 0.5

@traceable
def get_chat_completion(message: str, attached_filename: str = None, model: str = None) -> str:
    """Sends a message to the AI and retrieves the reply, including database context."""
    db_context = ""
    needs_context = True if attached_filename else laya_decide_if_context_needed(message)
    
    if needs_context:
        db_context = get_database_context(message, attached_filename)
    
    system_prompt = "You are a very helpful AI assistant."
    if db_context:
        system_prompt += f" Use the provided database context to answer the user's query.\n\nADDITIONAL DOCUMENTS/CONTEXT:\n{db_context}"

    response = client.chat.completions.create(
        model=model or settings.LLM_MODEL1,
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
    
    if not response.choices:
        error_info = getattr(response, "error", "Unknown AI Provider Error")
        if isinstance(error_info, dict):
            error_msg = error_info.get("message", str(error_info))
        else:
            error_msg = str(error_info)
        return f"⚠️ **AI Provider Error**: {error_msg}"
        
    return response.choices[0].message.content
