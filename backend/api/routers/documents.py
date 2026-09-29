from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import io
import hashlib
from core.database import get_db_connection

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        os.makedirs("uploads", exist_ok=True)
        content = await file.read()
        
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
        
        file_path = f"uploads/{file.filename}"
        file_url = f"local://{os.path.abspath(file_path)}"
        
        if not file_exists:
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            upload_message = f"File {file.filename} uploaded successfully"
        else:
            upload_message = f"File {file.filename} already exists (duplicate not saved)"
            
        extracted_text = ""
        if file.content_type and file.content_type.startswith('image/'):
            if TESSERACT_AVAILABLE:
                try:
                    image = Image.open(io.BytesIO(content))
                    extracted_text = pytesseract.image_to_string(image)
                except Exception as e:
                    extracted_text = f"[OCR Failed: {e}]"
            else:
                extracted_text = "[Tesseract or Pillow not installed]"
        elif file.content_type and file.content_type.startswith('text/'):
            try:
                extracted_text = content.decode('utf-8')
            except Exception:
                extracted_text = "[Failed to decode text file]"
        elif file.content_type == 'application/pdf':
            try:
                import pypdf
                pdf_reader = pypdf.PdfReader(io.BytesIO(content))
                extracted_text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
            except ImportError:
                extracted_text = "[pypdf not installed]"
            except Exception as e:
                extracted_text = f"[PDF Parsing Failed: {e}]"

        if extracted_text.strip():
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO documents (filename, content, file_hash, file_url) VALUES (%s, %s, %s, %s) ON CONFLICT (filename) DO UPDATE SET content = EXCLUDED.content, file_hash = EXCLUDED.file_hash, file_url = EXCLUDED.file_url RETURNING id",
                            (file.filename, extracted_text.strip(), file_hash, file_url)
                        )
                        
                        conn.commit()
                upload_message += " and saved to database"
            except Exception as db_err:
                upload_message += f" but failed to save to DB: {db_err}"
                
        return {"filename": file.filename, "status": "success", "message": upload_message, "extracted_text": extracted_text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail="File upload failed")

@router.get("/documents")
async def get_all_documents():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, filename, file_url, file_hash FROM documents ORDER BY id DESC")
                rows = cur.fetchall()
        return {"documents": [{"id": r[0], "filename": r[1], "file_url": r[2], "file_hash": r[3]} for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch documents")

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    try:
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
                    
                    return {"status": "success", "message": "Document deleted"}
                raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete document")

@router.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT filename, content FROM documents WHERE id = %s", (doc_id,))
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"id": doc_id, "filename": row[0], "extracted_text": row[1]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch document content")
