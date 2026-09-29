from openai import OpenAI
from core.config import settings
from core.database import get_db_connection

try:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    embedder = None
    print("sentence_transformers not installed.")

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
                        (
                            SELECT c.chunk_text, d.filename, c.chunk_id
                            FROM chunks c
                            JOIN documents d ON c.doc_id = d.id
                            WHERE d.filename = %s
                            ORDER BY c.chunk_id ASC
                            LIMIT 3
                        )
                        UNION
                        (
                            SELECT c.chunk_text, d.filename, c.chunk_id
                            FROM chunks c
                            JOIN documents d ON c.doc_id = d.id
                            WHERE d.filename = %s
                            ORDER BY c.chunk_embedding <-> %s::vector
                            LIMIT 3
                        )
                        ORDER BY chunk_id ASC
                    """, (attached_filename, attached_filename, query_embedding))
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
client = OpenAI(
  base_url=settings.OPENROUTER_BASE_URL,
  api_key=settings.OPENROUTER_API_KEY,
)

def get_chat_completion(message: str, attached_filename: str = None) -> str:
    """Sends a message to the AI and retrieves the reply, including database context."""
    db_context = get_database_context(message, attached_filename)
    
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
