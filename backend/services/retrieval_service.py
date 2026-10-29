import json
import logging

import httpx
from langsmith import traceable

from core.config import settings
from core.database import db_cursor
from core.ml import embedder
from services.document_service import get_document_names
from services.tagging_service import generate_query_profile

logger = logging.getLogger(__name__)

_http = httpx.Client(timeout=10.0, headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"})

JEV_URL = "https://openrouter.ai/api/alpha/decisions"

_PROFILE_FIELDS = ("year", "grade", "subject", "topic", "subtopic")

# Phase 1: top 10 documents by how many profile fields match their metadata (case-insensitive substring
#          either way, so "8" matches "Grade 8"); if none match, every document in scope.
# Phase 2: the 5 chunks of those documents nearest to the query embedding.
#
# Distance: <-> is pgvector's L2 (Euclidean) distance. The embedder normalizes every vector to length 1,
#   so L2 = sqrt(2 - 2 * cosine): same order as cosine similarity, which the model is trained for.
#   0 = same direction, sqrt(2) ~ 1.41 = unrelated, 2 = opposite.
# shortcut: no distance cutoff, so the 5 nearest are returned even when all are far; add one if
#   off-topic excerpts reach the prompt.
_CONTEXT_SQL = """
    WITH scored AS (
        SELECT d.id FROM documents d,
        LATERAL (
            SELECT count(*) AS score FROM jsonb_each_text(%(profile)s::jsonb) q
            WHERE NULLIF(d.metadata->>q.key, '') IS NOT NULL
              AND (d.metadata->>q.key ILIKE '%%' || q.value || '%%'
                   OR q.value ILIKE '%%' || (d.metadata->>q.key) || '%%')
        ) s
        WHERE ({scope}) AND s.score > 0
        ORDER BY s.score DESC, d.id
        LIMIT 10
    ),
    top_docs AS (
        SELECT id FROM scored
        UNION ALL
        SELECT d.id FROM documents d WHERE ({scope}) AND NOT EXISTS (SELECT 1 FROM scored)
    )
    SELECT d.filename, c.chunk_text, c.previous_summary
    FROM chunks c
    JOIN documents d ON d.id = c.doc_id
    WHERE c.doc_id IN (SELECT id FROM top_docs)
    ORDER BY c.chunk_embedding <-> %(query)s::vector
    LIMIT 5
"""


@traceable
def get_database_context(query: str, attached_filename: str = None, session_id: str = None) -> str:
    """5 chunks for the query, narrowed by document metadata, then vector distance."""
    profile = generate_query_profile(query)
    # An attached file is already the chosen document, so its metadata is not scored
    metadata = {} if attached_filename else {
        k: v.strip() for k in _PROFILE_FIELDS if isinstance(v := profile.get(k), str) and v.strip()
    }
    params = {
        "query": str(embedder.encode_query(query).tolist()),
        "profile": json.dumps(metadata),
        "filename": attached_filename,
        "session_id": session_id,
    }
    scope = "d.filename = %(filename)s" if attached_filename else "d.session_id IS NULL OR d.session_id = %(session_id)s"
    try:
        with db_cursor() as cur:
            cur.execute(_CONTEXT_SQL.format(scope=scope), params)
            rows = cur.fetchall()
    except Exception:
        logger.exception("Error fetching database context")
        return ""
    if not rows:
        return ""
    excerpts = "".join(
        f"\n--- Excerpt {i} (from {filename}) ---\n"
        + (f"[Summary of preceding text: {summary}]\n" if summary else "")
        + text + "\n"
        for i, (filename, text, summary) in enumerate(rows, 1)
    )
    return "Relevant excerpts from knowledge base:\n" + excerpts


@traceable(run_type="llm", name="Jev")
def _ask_jev(payload: dict) -> dict:
    """Raw Jev request/response, so the trace shows the full prompt and answer."""
    response = _http.post(JEV_URL, json=payload)
    response.raise_for_status()
    return response.json()


@traceable
def decide_if_context_needed(message: str, history: list[tuple[str, str]], session_id: str = None) -> bool:
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
        result = _ask_jev(payload)
        if "error" in result:
            logger.warning("Jev API returned an error payload: %s", result["error"])
            return True
        return result.get("answers", {}).get("needs_context", {}).get("noul", 0.0) > 0.5
    except Exception:
        logger.exception("Error calling jev")
        return True
