import logging
from typing import Optional

from psycopg2.extras import Json, execute_values

from core.database import db_cursor
from core.ml import embedder
from services.display import format_metadata
from services.tagging_service import generate_chunk_summaries, generate_chunk_tags

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
            "SELECT chunk_id, metadata, chunk_text, previous_summary FROM chunks WHERE doc_id = %s ORDER BY chunk_id",
            (doc_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "chunk_id": chunk_id,
            "label": _label(position, metadata),
            "metadata_text": format_metadata(metadata, _NO_METADATA),
            "chunk_text": chunk_text,
            # The first chunk has no previous chunk to summarize
            "previous_summary_text": _summary_text(previous_summary) if position > 1 else None,
        }
        for position, (chunk_id, metadata, chunk_text, previous_summary) in enumerate(rows, start=1)
    ]


def get_chunk(chunk_id: int) -> Optional[dict]:
    """One chunk in the same display shape as get_document_chunks, or None if it is gone."""
    with db_cursor() as cur:
        cur.execute("SELECT doc_id FROM chunks WHERE chunk_id = %s", (chunk_id,))
        row = cur.fetchone()
    # shortcut: reads the whole document because the label needs the chunk's position; fine at current doc sizes
    return None if row is None else next((c for c in get_document_chunks(row[0]) if c["chunk_id"] == chunk_id), None)


def _summary_text(summary: Optional[str]) -> str:
    return "Summary of previous chunk:\n" + (summary or "No summary available.")


def _label(position: int, metadata: Optional[dict]) -> str:
    """e.g. "Chunk 3 · Table · Region = Asia · p.2"; chunks stored before typed chunking show only the number."""
    metadata = metadata or {}
    kind = {"paragraph": "Paragraph", "list": "List", "table": "Table", "table_group": "Table"}.get(metadata.get("type"))
    group = metadata.get("group_value")
    if group and metadata.get("group_column"):
        group = f"{metadata['group_column']} = {group}"
    page = f"p.{metadata['page']}" if metadata.get("page") else None
    return " · ".join(filter(None, [f"Chunk {position}", kind, group, page]))


class GenerationFailed(Exception):
    pass


def regenerate_chunk_metadata(chunk_id: int) -> Optional[dict]:
    """Re-tag one chunk and store the result. Returns the updated chunk, or None if the chunk is gone."""
    with db_cursor() as cur:
        cur.execute("SELECT chunk_text FROM chunks WHERE chunk_id = %s", (chunk_id,))
        row = cur.fetchone()
    if row is None:
        return None

    # Slow LLM call happens outside any transaction
    tags = generate_chunk_tags([row[0]])[0]
    if tags is None:
        raise GenerationFailed(f"Tag generation failed for chunk {chunk_id}")

    # Merge so the chunk's type, page and section survive re-tagging
    with db_cursor() as cur:
        cur.execute(
            """UPDATE chunks SET metadata = COALESCE(metadata, jsonb_build_object('document_id', doc_id)) || %s
               WHERE chunk_id = %s""",
            (Json({"tags": tags}), chunk_id),
        )
    return get_chunk(chunk_id)


def regenerate_previous_summary(chunk_id: int) -> Optional[dict]:
    """Re-summarize the chunk before this one and store it as this chunk's previous_summary.

    Returns the updated chunk, or None if the chunk is gone or is its document's first chunk.
    """
    with db_cursor() as cur:
        cur.execute(
            """SELECT p.chunk_text FROM chunks c
               JOIN chunks p ON p.doc_id = c.doc_id AND p.chunk_id < c.chunk_id
               WHERE c.chunk_id = %s ORDER BY p.chunk_id DESC LIMIT 1""",
            (chunk_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None

    # Slow LLM call happens outside any transaction
    summary = generate_chunk_summaries([row[0]])[0]
    if summary is None:
        raise GenerationFailed(f"Summary generation failed for chunk {chunk_id}")

    with db_cursor() as cur:
        cur.execute("UPDATE chunks SET previous_summary = %s WHERE chunk_id = %s", (summary, chunk_id))
    return get_chunk(chunk_id)
