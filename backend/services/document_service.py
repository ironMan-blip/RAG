import io
import hashlib
from core.database import get_db_connection
from services.chunk_service import create_chunks_for_document, delete_chunks_for_document

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

def extract_text(content: bytes, content_type: str) -> str:
    extracted_text = ""
    if content_type and content_type.startswith('image/'):
        if TESSERACT_AVAILABLE:
            try:
                image = Image.open(io.BytesIO(content))
                extracted_text = pytesseract.image_to_string(image)
            except Exception as e:
                extracted_text = f"[OCR Failed: {e}]"
        else:
            extracted_text = "[Tesseract or Pillow not installed]"
    elif content_type and content_type.startswith('text/'):
        try:
            extracted_text = content.decode('utf-8')
        except Exception:
            extracted_text = "[Failed to decode text file]"
    elif content_type == 'application/pdf':
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(content))
            extracted_text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
        except ImportError:
            extracted_text = "[pypdf not installed]"
        except Exception as e:
            extracted_text = f"[PDF Parsing Failed: {e}]"
    else:
        try:
            extracted_text = content.decode('utf-8')
        except Exception:
            extracted_text = ""
    return extracted_text

def process_and_save_document(file_name: str, content: bytes, content_type: str, source_id: str, session_id: str = None) -> tuple[str, str]:
    file_hash = hashlib.sha256(content).hexdigest()
    file_exists = False
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM documents WHERE file_hash = %s", (file_hash,))
                if cur.fetchone():
                    file_exists = True
    except Exception as db_err:
        print(f"Error checking existing hash in DB: {db_err}")
    
    if not file_exists:
        upload_message = f"File {file_name} uploaded successfully"
    else:
        upload_message = f"File {file_name} already exists (duplicate not saved)"
        
    extracted_text = extract_text(content, content_type)

    if extracted_text.strip():
        try:
            source_name = None
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT source_name FROM source WHERE uuid = %s", (source_id,))
                    source_row = cur.fetchone()
                    metadata_json = None
                    if source_row:
                        source_name = source_row[0]
                        if source_name == 'tools':
                            session_id = None
                            try:
                                from services.llm_service import generate_tags_for_chunk
                                import json
                                # Use up to first 20000 characters to avoid huge payload while getting a good summary
                                metadata_str = generate_tags_for_chunk(extracted_text.strip()[:20000])
                                parsed_metadata = json.loads(metadata_str)
                                metadata_json = json.dumps(parsed_metadata)
                            except Exception as e:
                                print(f"Failed to generate/parse document metadata JSON: {e}")

                    cur.execute(
                        "INSERT INTO documents (filename, file_hash, source_id, session_id, metadata) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (filename) DO UPDATE SET file_hash = EXCLUDED.file_hash, source_id = EXCLUDED.source_id, session_id = EXCLUDED.session_id, metadata = EXCLUDED.metadata RETURNING id",
                        (file_name, file_hash, source_id, session_id, metadata_json)
                    )
                    doc_id = cur.fetchone()[0]
                        
                    conn.commit()
            
            create_chunks_for_document(doc_id, extracted_text.strip(), source_name)
            
            upload_message += " and saved to database"
        except Exception as db_err:
            upload_message += f" but failed to save to DB: {db_err}"
            
    return upload_message, extracted_text.strip()

def get_all_documents(session_id: str = None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if session_id:
                cur.execute("""
                    SELECT d.id, d.filename, d.file_hash, s.source_name 
                    FROM documents d 
                    LEFT JOIN source s ON d.source_id = s.uuid 
                    WHERE d.session_id IS NULL OR d.session_id = %s
                    ORDER BY d.id DESC
                """, (session_id,))
            else:
                cur.execute("""
                    SELECT d.id, d.filename, d.file_hash, s.source_name 
                    FROM documents d 
                    LEFT JOIN source s ON d.source_id = s.uuid 
                    ORDER BY d.id DESC
                """)
            rows = cur.fetchall()
    docs = []
    for r in rows:
        tag_str = r[3] or "unknown"
        if 'chat' in tag_str:
            tag_label = 'Chat Interface'
            bg_color = '#e0e7ff'
            text_color = '#4f46e5'
        elif 'library' in tag_str:
            tag_label = 'Library'
            bg_color = '#dcfce7'
            text_color = '#16a34a'
        elif 'tools' in tag_str:
            tag_label = 'Tools'
            bg_color = '#fef3c7'
            text_color = '#d97706'
        else:
            tag_label = tag_str
            bg_color = '#f1f5f9'
            text_color = '#64748b'
            
        docs.append({
            "id": r[0],
            "filename": r[1],
            "file_hash": r[2],
            "tag": tag_str,
            "tag_label": tag_label,
            "tag_bg_color": bg_color,
            "tag_text_color": text_color
        })
    return docs

def delete_document(doc_id: int) -> bool:
    try:
        delete_chunks_for_document(doc_id)
    except Exception as e:
        print(f"Failed to delete chunks: {e}")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s RETURNING id", (doc_id,))
            doc = cur.fetchone()
            conn.commit()
            if doc:
                return True
            return False
