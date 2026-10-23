import json
import logging

from langsmith import traceable

from core.database import db_cursor
from core.ml import embedder
from services.document_service import get_document_names
from services.tagging_service import decide_needs_context, generate_query_profile

logger = logging.getLogger(__name__)

_PROFILE_FIELDS = ("year", "grade", "subject", "topic", "subtopic")

# Phase 1: top 10 documents by how many profile fields match their metadata (case-insensitive substring
#          either way, so "8" matches "Grade 8"); if none match, every document in scope.
# Phase 2: top 20 of their chunks by how many query keywords hit a chunk tag; ties go to the closer chunk.
# Phase 3: the 5 of those nearest to the query embedding.
# shortcut: the fallback scores tags on every visible chunk, add a cap if the corpus grows large.
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
    ),
    top_chunks AS (
        SELECT c.chunk_id, c.chunk_embedding <-> %(query)s::vector AS distance
        FROM chunks c
        WHERE c.doc_id IN (SELECT id FROM top_docs)
        ORDER BY
            (SELECT count(*) FROM unnest(%(keywords)s::text[]) kw
             WHERE EXISTS (SELECT 1 FROM jsonb_array_elements_text(c.metadata->'tags') t
                           WHERE t ILIKE '%%' || kw || '%%')) DESC,
            distance
        LIMIT 20
    )
    SELECT d.filename, c.chunk_text, c.previous_summary
    FROM top_chunks tc
    JOIN chunks c USING (chunk_id)
    JOIN documents d ON d.id = c.doc_id
    ORDER BY tc.distance
    LIMIT 5
"""


@traceable
def get_database_context(query: str, attached_filename: str = None, session_id: str = None) -> str:
    """5 chunks for the query, narrowed by document metadata, then chunk tags, then vector distance."""
    profile = generate_query_profile(query)
    # An attached file is already the chosen document, so its metadata is not scored
    metadata = {} if attached_filename else {
        k: v.strip() for k in _PROFILE_FIELDS if isinstance(v := profile.get(k), str) and v.strip()
    }
    params = {
        "query": str(embedder.encode_query(query).tolist()),
        "profile": json.dumps(metadata),
        "keywords": [k.strip() for k in profile.get("keywords", []) if isinstance(k, str) and k.strip()],
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


@traceable
def decide_if_context_needed(message: str, history: list[tuple[str, str]], session_id: str = None) -> bool:
    """Asks the local model whether the documents are needed for this query. Defaults to True on failure."""
    try:
        doc_names = get_document_names(session_id)
    except Exception:
        logger.exception("Error listing documents")
        return True
    documents = "\n".join(f"{i}. {name}" for i, name in enumerate(doc_names, 1)) or "None"
    chat = "\n".join(f"User: {u}\nBot: {b}" for u, b in history) or "None"
    return decide_needs_context(f"Request: {message}\n\nAvailable documents:\n{documents}\n\nRecent chat:\n{chat}")
