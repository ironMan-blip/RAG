import logging
from typing import Optional

from psycopg2.extras import Json, execute_values

from core.database import db_cursor
from core.ml import embedder
from services.display import format_metadata
from services.tagging_service import generate_chunk_tags

logger = logging.getLogger(__name__)

# Chunk metadata keys produced by services.chunker, stored alongside document_id and tags
_NO_METADATA = "No metadata available for this chunk."
_CHUNK_FIELDS = ("type", "page", "section", "table_id", "group_column", "group_value")


def embed_chunks(chunks: list[dict], summaries: list[Optional[str]]) -> tuple[list[list[float]], list[str]]:
    """Embed each chunk's text; a chunk longer than the embedder reads is embedded from its summary.

    Returns the embeddings and, per chunk, what was embedded ("text" or "summary").
    """
    inputs, sources = [], []
    for chunk, summary in zip(chunks, summaries):
        too_long = len(embedder.tokenizer(chunk["text"])["input_ids"]) > embedder.max_seq_length
        if too_long and summary:
            inputs.append(summary)
            sources.append("summary")
        else:
            if too_long:
                logger.warning("Chunk exceeds %d tokens and has no summary; embedding truncated text",
                               embedder.max_seq_length)
            inputs.append(chunk["text"])
            sources.append("text")
    # Small batches: chunks have no size cap, and padding a batch to its longest chunk costs memory
    embeddings = embedder.encode_document(inputs, batch_size=4).tolist() if inputs else []
    return embeddings, sources


def _chunk_metadata(doc_id: int, chunk: dict, tags: Optional[list[str]], embedded_from: str) -> dict:
    metadata = {"document_id": doc_id, **{k: chunk[k] for k in _CHUNK_FIELDS if k in chunk},
                "embedded_from": embedded_from}
    if tags:
        metadata["tags"] = tags
    return metadata


def replace_chunks(cur, doc_id: int, chunks: list[dict], embeddings: list[list[float]], embedded_from: list[str],
                   tags: list[Optional[list[str]]], previous_summaries: list[Optional[str]]):
    """Swap a document's chunks for new ones; runs in the caller's transaction."""
    cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
    execute_values(
        cur,
        "INSERT INTO chunks (doc_id, chunk_text, chunk_embedding, metadata, previous_summary) VALUES %s",
        [(doc_id, c["text"], e, Json(_chunk_metadata(doc_id, c, t, f)), s)
         for c, e, f, t, s in zip(chunks, embeddings, embedded_from, tags, previous_summaries)],
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
            "label": _label(position, metadata),
            "metadata_text": format_metadata(metadata, _NO_METADATA),
        }
        for position, (chunk_id, metadata) in enumerate(rows, start=1)
    ]


def _label(position: int, metadata: Optional[dict]) -> str:
    """e.g. "Chunk 3 · Table · Region = Asia · p.2"; chunks stored before typed chunking show only the number."""
    metadata = metadata or {}
    kind = {"paragraph": "Paragraph", "list": "List", "table": "Table", "table_group": "Table"}.get(metadata.get("type"))
    group = metadata.get("group_value")
    if group and metadata.get("group_column"):
        group = f"{metadata['group_column']} = {group}"
    page = f"p.{metadata['page']}" if metadata.get("page") else None
    return " · ".join(filter(None, [f"Chunk {position}", kind, group, page]))


class TaggingFailed(Exception):
    pass


def regenerate_chunk_metadata(chunk_id: int) -> Optional[str]:
    """Re-tag one chunk and store the result. Returns its new metadata text, or None if the chunk is gone."""
    with db_cursor() as cur:
        cur.execute("SELECT chunk_text FROM chunks WHERE chunk_id = %s", (chunk_id,))
        row = cur.fetchone()
    if row is None:
        return None

    # Slow LLM call happens outside any transaction
    tags = generate_chunk_tags([row[0]])[0]
    if tags is None:
        raise TaggingFailed(f"Tag generation failed for chunk {chunk_id}")

    # Merge so the chunk's type, page and section survive re-tagging
    with db_cursor() as cur:
        cur.execute(
            """UPDATE chunks SET metadata = COALESCE(metadata, jsonb_build_object('document_id', doc_id)) || %s
               WHERE chunk_id = %s RETURNING metadata""",
            (Json({"tags": tags}), chunk_id),
        )
        updated = cur.fetchone()
    return None if updated is None else format_metadata(updated[0], _NO_METADATA)
