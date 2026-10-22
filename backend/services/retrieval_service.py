import logging
from typing import Optional

import httpx
from langsmith import traceable

from core.config import settings
from core.database import db_cursor
from core.ml import embedder
from services.document_service import get_document_names

logger = logging.getLogger(__name__)

_http = httpx.Client(timeout=10.0, headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"})

JEV_URL = "https://openrouter.ai/api/alpha/decisions"

# Nearest chunks plus, for paragraph hits, the paragraphs right before and after them
# (a paragraph often depends on its neighbours). Table chunks are returned alone.
_CONTEXT_SQL = """
    WITH hits AS (
        SELECT chunk_id, row_number() OVER (ORDER BY distance) AS rank FROM (
            SELECT c.chunk_id, c.chunk_embedding <-> %(query)s::vector AS distance
            FROM chunks c
            JOIN documents d ON c.doc_id = d.id
            WHERE {scope}
            ORDER BY distance
            LIMIT %(limit)s
        ) nearest
    ),
    doc_chunks AS (
        SELECT c.chunk_id, c.doc_id, c.chunk_text, c.previous_summary, c.metadata->>'type' AS type,
               row_number() OVER (PARTITION BY c.doc_id ORDER BY c.chunk_id) AS pos
        FROM chunks c
        WHERE c.doc_id IN (SELECT c2.doc_id FROM chunks c2 JOIN hits h ON h.chunk_id = c2.chunk_id)
    )
    SELECT o.doc_id, o.pos, o.chunk_text, o.previous_summary, d.filename, MIN(h.rank) AS rank
    FROM hits h
    JOIN doc_chunks hc ON hc.chunk_id = h.chunk_id
    JOIN doc_chunks o ON o.doc_id = hc.doc_id
        AND (o.pos = hc.pos OR (hc.type = 'paragraph' AND abs(o.pos - hc.pos) = 1))
    JOIN documents d ON d.id = o.doc_id
    GROUP BY o.doc_id, o.pos, o.chunk_text, o.previous_summary, d.filename
"""


def _excerpt_runs(rows) -> list[tuple[str, Optional[str], list[str]]]:
    """Join chunks adjacent in a document into one excerpt: (filename, summary before it, texts).

    Documents come in order of their best hit; chunks within a document in reading order.
    """
    best = {}
    for doc_id, _, _, _, _, rank in rows:
        best[doc_id] = min(rank, best.get(doc_id, rank))
    runs, prev = [], None
    for doc_id, pos, text, summary, filename, _ in sorted(rows, key=lambda r: (best[r[0]], r[0], r[1])):
        if prev == (doc_id, pos - 1):
            runs[-1][2].append(text)
        else:
            runs.append((filename, summary, [text]))
        prev = (doc_id, pos)
    return runs


@traceable
def get_database_context(query: str, attached_filename: str = None, session_id: str = None) -> str:
    """Nearest chunks to the query: from the attached file if any, else from all visible documents."""
    query_embedding = str(embedder.encode_query(query).tolist())
    try:
        with db_cursor() as cur:
            if attached_filename:
                cur.execute(_CONTEXT_SQL.format(scope="d.filename = %(filename)s"),
                            {"query": query_embedding, "limit": 3, "filename": attached_filename})
            else:
                cur.execute(_CONTEXT_SQL.format(scope="d.session_id IS NULL OR d.session_id = %(session_id)s"),
                            {"query": query_embedding, "limit": 5, "session_id": session_id})
            rows = cur.fetchall()
    except Exception:
        logger.exception("Error fetching database context")
        return ""
    if not rows:
        return ""
    excerpts = "".join(
        f"\n--- Excerpt {i} (from {filename}) ---\n"
        + (f"[Summary of preceding text: {summary}]\n" if summary else "")
        + "\n\n".join(texts) + "\n"
        for i, (filename, summary, texts) in enumerate(_excerpt_runs(rows), 1)
    )
    return "Relevant excerpts from knowledge base:\n" + excerpts


@traceable
def jev_decide_if_context_needed(message: str, history: list[tuple[str, str]], session_id: str = None) -> bool:
    """Uses Jev to decide if external documents are needed for this query. Defaults to True on failure."""
    try:
        doc_names = get_document_names(session_id)
        payload = {
            "model": "typesafe/jev-1.13",
            "state": {
                "request": message,
                "available_documents": "\n".join(f"{i}. {name}" for i, name in enumerate(doc_names, 1)) or "None",
                "chat_history": "\n".join(f"User: {u}\nBot: {b}" for u, b in history) or "None",
            },
            "questions": {
                "needs_context": {
                    "type": "noul",
                    "instructions": "Does `request` require looking up facts, data, or external documents? The following documents are available in the database: `available_documents`. Consider the recent chat context: `chat_history`.",
                    "criteria": {
                        "false": "casual greetings, conversational chat, or statements that require no context",
                        "true": "factual queries or questions that need external documents"
                    }
                }
            }
        }
        response = _http.post(JEV_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            logger.warning("Jev API returned an error payload: %s", result["error"])
            return True
        return result.get("answers", {}).get("needs_context", {}).get("noul", 0.0) > 0.5
    except Exception:
        logger.exception("Error calling jev")
        return True
