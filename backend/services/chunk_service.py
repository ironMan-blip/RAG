from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from psycopg2.extras import Json, execute_values

from core.database import db_cursor
from core.ml import embedder
from services.display import format_metadata
from services.tagging_service import generate_chunk_tags

# No overlap: each chunk carries a summary of the one before it instead
_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)


def split_text(text: str) -> list[str]:
    return _splitter.split_text(text)


def _chunk_metadata(doc_id: int, tags: Optional[list[str]]) -> Optional[dict]:
    return {"document_id": doc_id, "tags": tags} if tags else None


def replace_chunks(cur, doc_id: int, chunks: list[str], tags: list[Optional[list[str]]],
                   previous_summaries: list[Optional[str]]):
    """Swap a document's chunks for new ones; runs in the caller's transaction."""
    embeddings = embedder.encode(chunks).tolist() if chunks else []
    cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
    execute_values(
        cur,
        "INSERT INTO chunks (doc_id, chunk_text, chunk_embedding, metadata, previous_summary) VALUES %s",
        [(doc_id, c, e, Json(m) if (m := _chunk_metadata(doc_id, t)) else None, s)
         for c, e, t, s in zip(chunks, embeddings, tags, previous_summaries)],
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
            "metadata_text": _metadata_text(metadata),
        }
        for position, (chunk_id, metadata) in enumerate(rows, start=1)
    ]


def _metadata_text(metadata) -> str:
    return format_metadata(metadata, "No metadata available for this chunk.")


class TaggingFailed(Exception):
    pass


def regenerate_chunk_metadata(chunk_id: int) -> Optional[str]:
    """Re-tag one chunk and store the result. Returns its new metadata text, or None if the chunk is gone."""
    with db_cursor() as cur:
        cur.execute("SELECT chunk_text, doc_id FROM chunks WHERE chunk_id = %s", (chunk_id,))
        row = cur.fetchone()
    if row is None:
        return None
    chunk_text, doc_id = row

    # Slow LLM call happens outside any transaction
    tags = generate_chunk_tags([chunk_text])[0]
    if tags is None:
        raise TaggingFailed(f"Tag generation failed for chunk {chunk_id}")

    metadata = _chunk_metadata(doc_id, tags)
    with db_cursor() as cur:
        cur.execute("UPDATE chunks SET metadata = %s WHERE chunk_id = %s", (Json(metadata), chunk_id))
        if cur.rowcount == 0:
            return None
    return _metadata_text(metadata)
