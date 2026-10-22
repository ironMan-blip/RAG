import hashlib
import io
import logging
from typing import Optional

import pypdf
import pytesseract
from PIL import Image
from psycopg2.extras import Json

from core.database import db_cursor
from services.chunk_service import replace_chunks, split_text
from services.display import format_metadata
from services.tagging_service import generate_chunk_summaries, generate_chunk_tags, generate_document_metadata

logger = logging.getLogger(__name__)

# Upload origins, keyed by the name clients send; values are source.uuid rows from schema.sql
SOURCE_IDS = {
    'library': '79279d88-e2c3-4a36-9da6-3f02dd71796b',
    'tools': 'b8118424-5418-47b7-a661-8bb768aa8ef5',
    'chat': '20a26963-d20c-469f-8837-620321d589a6'
}

# source uuid -> (label, background color, text color) for the document tag badge
TAG_STYLES = {
    SOURCE_IDS['chat']: ('Chat Interface', '#e0e7ff', '#4f46e5'),
    SOURCE_IDS['library']: ('Library', '#dcfce7', '#16a34a'),
    SOURCE_IDS['tools']: ('Tools', '#fef3c7', '#d97706'),
}


def extract_text(content: bytes, content_type: Optional[str]) -> str:
    content_type = content_type or ""
    try:
        if content_type.startswith('image/'):
            return pytesseract.image_to_string(Image.open(io.BytesIO(content)))
        if content_type == 'application/pdf':
            reader = pypdf.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        return content.decode('utf-8')
    except Exception as e:
        logger.warning("Text extraction failed for %s: %s", content_type, e)
        return ""


def _is_unchanged(cur, file_name: str, file_hash: str, source_id: str, session_id: Optional[str]) -> bool:
    cur.execute(
        """SELECT 1 FROM documents
           WHERE filename = %s AND file_hash = %s AND source_id = %s
             AND session_id IS NOT DISTINCT FROM %s""",
        (file_name, file_hash, source_id, session_id),
    )
    return cur.fetchone() is not None


def process_and_save_document(file_name: str, content: bytes, content_type: str, source_id: str, session_id: str = None) -> str:
    """Extract, chunk, embed and store a file. Returns a status message."""
    text = extract_text(content, content_type).strip()
    if not text:
        return f"File {file_name} has no extractable text (not saved)"

    is_tool = source_id == SOURCE_IDS['tools']
    if is_tool:
        session_id = None  # tool documents are global
    file_hash = hashlib.sha256(content).hexdigest()

    with db_cursor() as cur:
        if _is_unchanged(cur, file_name, file_hash, source_id, session_id):
            return f"File {file_name} already exists (duplicate not saved)"

    # Slow work (LLM tagging) happens before the write transaction opens
    chunks = split_text(text)
    if is_tool:
        doc_metadata, chunk_tags = generate_document_metadata(text), generate_chunk_tags(chunks)
    else:
        doc_metadata, chunk_tags = None, [None] * len(chunks)
    # Chunk i stores the summary of chunk i-1; the first chunk has none
    previous_summaries = [None] + generate_chunk_summaries(chunks[:-1])

    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO documents (filename, file_hash, source_id, session_id, metadata)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (filename) DO UPDATE SET
                   file_hash = EXCLUDED.file_hash, source_id = EXCLUDED.source_id,
                   session_id = EXCLUDED.session_id, metadata = EXCLUDED.metadata
               RETURNING id""",
            (file_name, file_hash, source_id, session_id, Json(doc_metadata) if doc_metadata else None),
        )
        replace_chunks(cur, cur.fetchone()[0], chunks, chunk_tags, previous_summaries)

    return f"File {file_name} uploaded successfully and saved to database"


def get_all_documents(search: str = ""):
    # Escape LIKE wildcards so the search matches the filename text literally
    pattern = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with db_cursor() as cur:
        cur.execute("""
            SELECT d.id, d.filename, d.source_id, s.source_name, d.metadata
            FROM documents d
            LEFT JOIN source s ON d.source_id = s.uuid
            WHERE d.filename ILIKE %s
            ORDER BY d.id DESC
        """, (pattern,))
        rows = cur.fetchall()
    docs = []
    for doc_id, filename, source_id, source_name, metadata in rows:
        label, bg_color, text_color = TAG_STYLES.get(source_id, (source_name or "unknown", '#f1f5f9', '#64748b'))
        docs.append({
            "id": doc_id,
            "filename": filename,
            "tag_label": label,
            "tag_bg_color": bg_color,
            "tag_text_color": text_color,
            "metadata_text": format_metadata(metadata, "No metadata available for this document."),
        })
    return docs


def get_document_names(session_id: str = None) -> list[str]:
    """Filenames visible to a chat: global documents plus that session's attachments."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT filename FROM documents WHERE session_id IS NULL OR session_id = %s ORDER BY id DESC",
            (session_id,),
        )
        return [row[0] for row in cur.fetchall()]


def delete_document(doc_id: int) -> bool:
    # chunks go with it via ON DELETE CASCADE
    with db_cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s RETURNING id", (doc_id,))
        return cur.fetchone() is not None
