import os
import io
import hashlib
from fastapi import HTTPException
from core.database import get_db_connection

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

def process_and_save_document(file_name: str, content: bytes, content_type: str) -> tuple[str, str]:
    os.makedirs("uploads", exist_ok=True)
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
        for existing_filename in os.listdir("uploads"):
            existing_path = os.path.join("uploads", existing_filename)
            if os.path.isfile(existing_path):
                with open(existing_path, "rb") as f:
                    if hashlib.sha256(f.read()).hexdigest() == file_hash:
                        file_exists = True
                        break
    
    file_path = f"uploads/{file_name}"
    file_url = f"local://{os.path.abspath(file_path)}"
    
    if not file_exists:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        upload_message = f"File {file_name} uploaded successfully"
    else:
        upload_message = f"File {file_name} already exists (duplicate not saved)"
        
    extracted_text = extract_text(content, content_type)

    if extracted_text.strip():
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents (filename, content, file_hash, file_url) VALUES (%s, %s, %s, %s) ON CONFLICT (filename) DO UPDATE SET content = EXCLUDED.content, file_hash = EXCLUDED.file_hash, file_url = EXCLUDED.file_url RETURNING id",
                        (file_name, extracted_text.strip(), file_hash, file_url)
                    )
                    doc_id = cur.fetchone()[0]
                    conn.commit()
            
            # Create chunks for the newly saved/updated document
            from services.chunk_service import create_chunks_for_document
            create_chunks_for_document(doc_id, extracted_text.strip())
            
            upload_message += " and saved to database"
        except Exception as db_err:
            upload_message += f" but failed to save to DB: {db_err}"
            
    return upload_message, extracted_text.strip()

def get_all_documents():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, file_url, file_hash FROM documents ORDER BY id DESC")
            rows = cur.fetchall()
    return [{"id": r[0], "filename": r[1], "file_url": r[2], "file_hash": r[3]} for r in rows]

def delete_document(doc_id: int) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM documents WHERE id = %s", (doc_id,))
            doc = cur.fetchone()
            if doc:
                filename = doc[0]
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                conn.commit()
                
                file_path = os.path.join("uploads", filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                return True
            return False

def get_document_content(doc_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, content FROM documents WHERE id = %s", (doc_id,))
            row = cur.fetchone()
    if not row:
        return None
    return {"id": doc_id, "filename": row[0], "extracted_text": row[1]}
