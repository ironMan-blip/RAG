from fastapi import APIRouter, HTTPException, UploadFile, File
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import get_chat_completion
import os
import io

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        # Pass the frontend message to the AI service
        bot_reply = get_chat_completion(req.message)
        
        # Return the reply
        return ChatResponse(reply=bot_reply)
    except Exception as e:
        print(f"Error during AI request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

import hashlib

import psycopg2
from core.config import settings

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        os.makedirs("uploads", exist_ok=True)
        content = await file.read()
        
        file_hash = hashlib.sha256(content).hexdigest()
        file_exists = False
        
        # Check if hash already exists in DB
        try:
            conn = psycopg2.connect(settings.DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT id FROM documents WHERE file_hash = %s", (file_hash,))
            existing_doc = cur.fetchone()
            if existing_doc:
                file_exists = True
            cur.close()
            conn.close()
        except Exception as db_err:
            print(f"Error checking existing hash in DB: {db_err}")
            # Fallback to local disk check if DB fails
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
        
        # Check if the file is an image and extract text using Tesseract
        if file.content_type and file.content_type.startswith('image/'):
            if TESSERACT_AVAILABLE:
                try:
                    image = Image.open(io.BytesIO(content))
                    extracted_text = pytesseract.image_to_string(image)
                except Exception as e:
                    print(f"Error extracting text with Tesseract: {e}")
                    extracted_text = f"[OCR Failed: {e}]"
            else:
                extracted_text = "[Tesseract or Pillow not installed on backend]"
        elif file.content_type and file.content_type.startswith('text/'):
            try:
                extracted_text = content.decode('utf-8')
            except Exception:
                extracted_text = "[Failed to decode text file]"
        elif file.content_type and file.content_type == 'application/pdf':
            try:
                import pypdf
                pdf_reader = pypdf.PdfReader(io.BytesIO(content))
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text() or "")
                extracted_text = "\n".join(text_parts)
            except ImportError:
                extracted_text = "[pypdf not installed on backend]"
            except Exception as e:
                print(f"Error extracting text from PDF: {e}")
                extracted_text = f"[PDF Parsing Failed: {e}]"

        # Insert into database
        if extracted_text.strip():
            try:
                conn = psycopg2.connect(settings.DATABASE_URL)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO documents (filename, content, file_hash, file_url) VALUES (%s, %s, %s, %s) ON CONFLICT (filename) DO UPDATE SET content = EXCLUDED.content, file_hash = EXCLUDED.file_hash, file_url = EXCLUDED.file_url RETURNING id",
                    (file.filename, extracted_text.strip(), file_hash, file_url)
                )
                
                # Fetch the document id (either newly inserted or updated)
                result = cur.fetchone()
                if result:
                    doc_id = result[0]
                else:
                    cur.execute("SELECT id FROM documents WHERE filename = %s", (file.filename,))
                    doc_id = cur.fetchone()[0]
                
                # Update chunks for this document
                cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
                lines = extracted_text.strip().split('\n')
                chunk_lines = []
                for line in lines:
                    chunk_lines.append(line)
                    if len(chunk_lines) == 5:
                        cur.execute(
                            "INSERT INTO chunks (document_id, chunk_text) VALUES (%s, %s)",
                            (doc_id, '\n'.join(chunk_lines))
                        )
                        chunk_lines = []
                if chunk_lines:
                    cur.execute(
                        "INSERT INTO chunks (document_id, chunk_text) VALUES (%s, %s)",
                        (doc_id, '\n'.join(chunk_lines))
                    )
                
                conn.commit()
                cur.close()
                conn.close()
                upload_message += " and saved to database with chunks"
            except Exception as db_err:
                print(f"Database insertion error: {db_err}")
                upload_message += f" but failed to save to DB: {db_err}"
                
        return {
            "filename": file.filename, 
            "status": "success", 
            "message": upload_message,
            "extracted_text": extracted_text.strip()
        }
    except Exception as e:
        print(f"Error during file upload: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(doc_id: int):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT chunk_id, chunk_text FROM chunks WHERE document_id = %s ORDER BY chunk_id", (doc_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        chunks = [{"chunk_id": row[0], "chunk_text": row[1]} for row in rows]
        return {"document_id": doc_id, "chunks": chunks}
    except Exception as e:
        print(f"Error fetching chunks for document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chunks")

@router.get("/chunks")
async def get_all_chunks(limit: int = 100, offset: int = 0):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT chunk_id, document_id, chunk_text FROM chunks ORDER BY chunk_id LIMIT %s OFFSET %s", (limit, offset))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        chunks = [{"chunk_id": row[0], "document_id": row[1], "chunk_text": row[2]} for row in rows]
        return {"chunks": chunks, "limit": limit, "offset": offset}
    except Exception as e:
        print(f"Error fetching all chunks: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chunks")

@router.get("/documents")
async def get_all_documents():
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, filename, file_url, file_hash FROM documents ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        documents = [{"id": row[0], "filename": row[1], "file_url": row[2], "file_hash": row[3]} for row in rows]
        return {"documents": documents}
    except Exception as e:
        print(f"Error fetching documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch documents")

@router.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: int):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT filename, content FROM documents WHERE id = %s", (doc_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return {"id": doc_id, "filename": row[0], "extracted_text": row[1]}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching document content: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch document content")

