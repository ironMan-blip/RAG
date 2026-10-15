from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from psycopg2.extras import Json, execute_values

from core.database import db_cursor
from core.ml import embedder
from services.display import format_metadata

_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def split_text(text: str) -> list[str]:
    return _splitter.split_text(text)


def replace_chunks(cur, doc_id: int, chunks: list[str], metadata: list[Optional[dict]]):
    """Swap a document's chunks for new ones; runs in the caller's transaction."""
    embeddings = embedder.encode(chunks).tolist() if chunks else []
    cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
    execute_values(
        cur,
        "INSERT INTO chunks (doc_id, chunk_text, chunk_embedding, metadata) VALUES %s",
        [(doc_id, c, e, Json(m) if m else None) for c, e, m in zip(chunks, embeddings, metadata)],
    )


def get_document_chunks(doc_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT chunk_id, metadata FROM chunks WHERE doc_id = %s ORDER BY chunk_id",
            (doc_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "chunk_id": chunk_id,
            "label": f"Chunk {position}",
            "metadata_text": format_metadata(metadata, "No metadata available for this chunk."),
        }
        for position, (chunk_id, metadata) in enumerate(rows, start=1)
    ]
