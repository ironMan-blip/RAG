"""Library reads and deletes for saved documents; uploads are services.ingest_service."""
import json

from core.database import db_cursor
from core.sources import SOURCE_IDS, TAG_STYLES


def get_upload_sources() -> list[dict]:
    """Sources a client may upload to (chat is implicit), with label and accent color for the UI."""
    return [
        {"value": name, "label": TAG_STYLES[SOURCE_IDS[name]][0], "color": TAG_STYLES[SOURCE_IDS[name]][2]}
        for name in ('library', 'tools')
    ]


def get_all_documents(search: str = ""):
    # Escape LIKE wildcards so the search matches the filename text literally
    pattern = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with db_cursor() as cur:
        cur.execute("""
            SELECT d.id, d.filename, d.source_id, s.source_name, d.metadata,
                   EXISTS (SELECT 1 FROM chunks c WHERE c.doc_id = d.id AND c.status = 'unfinished')
            FROM documents d
            LEFT JOIN source s ON d.source_id = s.uuid
            WHERE d.filename ILIKE %s AND d.status = 'ready'
            ORDER BY d.id DESC
        """, (pattern,))
        rows = cur.fetchall()
    docs = []
    for doc_id, filename, source_id, source_name, metadata, unfinished in rows:
        label, bg_color, text_color = TAG_STYLES.get(source_id, (source_name or "unknown", '#f1f5f9', '#64748b'))
        docs.append({
            "id": doc_id,
            "filename": filename,
            "tag_label": label,
            "tag_bg_color": bg_color,
            "tag_text_color": text_color,
            "metadata_text": json.dumps(metadata, indent=2) if metadata else "No metadata available for this document.",
            "unfinished_text": "Some chunks failed to generate. Open the document to regenerate them." if unfinished else None,
        })
    return docs


def get_document_names(session_id: str = None) -> list[str]:
    """Filenames visible to a chat: global documents plus that session's attachments."""
    with db_cursor() as cur:
        cur.execute(
            """SELECT filename FROM documents
               WHERE status = 'ready' AND (session_id IS NULL OR session_id = %s) ORDER BY id DESC""",
            (session_id,),
        )
        return [row[0] for row in cur.fetchall()]


def delete_document(doc_id: int) -> bool:
    # chunks go with it via ON DELETE CASCADE; an uploading document is stopped through its upload instead
    with db_cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s AND status = 'ready' RETURNING id", (doc_id,))
        return cur.fetchone() is not None
