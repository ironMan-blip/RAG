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
    return extracted_text

def process_and_save_document(file_name: str, content: bytes, content_type: str, source_id: str) -> tuple[str, str]:
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
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents (filename, file_hash, source_id) VALUES (%s, %s, %s) ON CONFLICT (filename) DO UPDATE SET file_hash = EXCLUDED.file_hash, source_id = EXCLUDED.source_id RETURNING id",
                        (file_name, file_hash, source_id)
                    )
                    doc_id = cur.fetchone()[0]
                    conn.commit()
            
            create_chunks_for_document(doc_id, extracted_text.strip())
            
            upload_message += " and saved to database"
        except Exception as db_err:
            upload_message += f" but failed to save to DB: {db_err}"
            
    return upload_message, extracted_text.strip()

def get_all_documents():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, file_hash FROM documents ORDER BY id DESC")
            rows = cur.fetchall()
    return [{"id": r[0], "filename": r[1], "file_hash": r[2]} for r in rows]

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
