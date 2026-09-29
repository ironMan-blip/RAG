from core.database import get_db_connection
try:
    from sentence_transformers import SentenceTransformer
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    # Load model (dimension 384)
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
except ImportError:
    embedder = None
    text_splitter = None

def create_chunks_for_document(doc_id: int, text: str):
    if not embedder or not text_splitter:
        print("SentenceTransformer or Langchain Text Splitters not installed.")
        return
        
    chunks = text_splitter.split_text(text)
    
    delete_chunks_for_document(doc_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for chunk in chunks:
                embedding = embedder.encode(chunk).tolist()
                cur.execute(
                    "INSERT INTO chunks (doc_id, chunk_text, chunk_embedding) VALUES (%s, %s, %s)",
                    (doc_id, chunk, embedding)
                )
        conn.commit()

def delete_chunks_for_document(doc_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
        conn.commit()

def process_all_existing_documents():
    """Convert all existing documents to chunks."""
    if not embedder or not text_splitter:
        print("Dependencies missing.")
        return
        
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content FROM documents WHERE content IS NOT NULL AND content != ''")
            docs = cur.fetchall()
            
            # Clear existing chunks first to avoid duplicates
            cur.execute("TRUNCATE TABLE chunks RESTART IDENTITY CASCADE;")
            
            for doc_id, text in docs:
                chunks = text_splitter.split_text(text)
                for chunk in chunks:
                    embedding = embedder.encode(chunk).tolist()
                    cur.execute(
                        "INSERT INTO chunks (doc_id, chunk_text, chunk_embedding) VALUES (%s, %s, %s)",
                        (doc_id, chunk, embedding)
                    )
        conn.commit()
