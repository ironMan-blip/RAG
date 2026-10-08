from core.database import get_db_connection
from core.ml import embedder

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
except ImportError:
    text_splitter = None

def create_chunks_for_document(doc_id: int, text: str, source_name: str = None):
    if not embedder or not text_splitter:
        print("SentenceTransformer or Langchain Text Splitters not installed.")
        return
        
    chunks = text_splitter.split_text(text)
    
    delete_chunks_for_document(doc_id)
    
    from services.llm_service import generate_tags_for_chunk
    import json
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for chunk in chunks:
                embedding = embedder.encode(chunk).tolist()
                metadata_json = None
                if source_name == 'tools':
                    metadata_str = generate_tags_for_chunk(chunk)
                    try:
                        metadata_json = json.dumps(json.loads(metadata_str))
                    except Exception as e:
                        print(f"Failed to parse metadata JSON: {e}")
                        
                cur.execute(
                    "INSERT INTO chunks (doc_id, chunk_text, chunk_embedding, metadata) VALUES (%s, %s, %s, %s)",
                    (doc_id, chunk, embedding, metadata_json)
                )
        conn.commit()

def delete_chunks_for_document(doc_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
        conn.commit()
