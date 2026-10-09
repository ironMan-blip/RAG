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
        error_msg = "SentenceTransformer or Langchain Text Splitters not installed."
        print(error_msg)
        raise Exception(error_msg)
        
    chunks = text_splitter.split_text(text)
    
    delete_chunks_for_document(doc_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for chunk in chunks:
                embedding = embedder.encode(chunk).tolist()
                metadata_json = None
                
                if source_name == 'tools':
                    try:
                        from services.llm_service import generate_tags_for_chunk
                        import json
                        metadata_str = generate_tags_for_chunk(chunk)
                        parsed_metadata = json.loads(metadata_str)
                        metadata_json = json.dumps(parsed_metadata)
                    except Exception as e:
                        print(f"Failed to generate/parse chunk metadata JSON: {e}")

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

def get_all_chunks():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.chunk_id, c.doc_id, d.filename, c.chunk_text, c.metadata
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                ORDER BY c.chunk_id DESC
            """)
            rows = cur.fetchall()
    chunks = []
    for r in rows:
        chunks.append({
            "chunk_id": r[0],
            "doc_id": r[1],
            "filename": r[2],
            "chunk_text": r[3],
            "metadata": r[4]
        })
    return chunks
