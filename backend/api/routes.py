from pydantic import BaseModel
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
                chunk_index = 1
                for line in lines:
                    chunk_lines.append(line)
                    if len(chunk_lines) == 5:
                        chunk_name = f"{file.filename}_chunk_{chunk_index}"
                        cur.execute(
                            "INSERT INTO chunks (document_id, chunk_name, chunk_text) VALUES (%s, %s, %s)",
                            (doc_id, chunk_name, '\n'.join(chunk_lines))
                        )
                        chunk_lines = []
                        chunk_index += 1
                if chunk_lines:
                    chunk_name = f"{file.filename}_chunk_{chunk_index}"
                    cur.execute(
                        "INSERT INTO chunks (document_id, chunk_name, chunk_text) VALUES (%s, %s, %s)",
                        (doc_id, chunk_name, '\n'.join(chunk_lines))
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
        cur.execute("SELECT chunk_id, chunk_name, chunk_text FROM chunks WHERE document_id = %s ORDER BY chunk_id", (doc_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        chunks = [{"chunk_id": row[0], "chunk_name": row[1], "chunk_text": row[2]} for row in rows]
        return {"document_id": doc_id, "chunks": chunks}
    except Exception as e:
        print(f"Error fetching chunks for document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chunks")

@router.get("/chunks")
async def get_all_chunks(limit: int = 100, offset: int = 0):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT c.chunk_id, c.document_id, c.chunk_name, c.chunk_text, d.filename 
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            ORDER BY c.chunk_id LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        chunks = [{"chunk_id": row[0], "document_id": row[1], "chunk_name": row[2], "chunk_text": row[3], "filename": row[4]} for row in rows]
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

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        
        # Optionally, get filename to delete local file
        cur.execute("SELECT filename FROM documents WHERE id = %s", (doc_id,))
        doc = cur.fetchone()
        
        if doc:
            filename = doc[0]
            # Delete from database
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            conn.commit()
            
            # Try to delete from local file system if it exists in uploads
            file_path = os.path.join("uploads", filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error removing local file {file_path}: {e}")
            
            message = "Document deleted successfully"
        else:
            raise HTTPException(status_code=404, detail="Document not found")
            
        cur.close()
        conn.close()
        
        return {"status": "success", "message": message}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")

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


class FileGroupCreate(BaseModel):
    name: str

class FileGroupAddDocument(BaseModel):
    document_id: int

@router.get("/file-groups")
async def get_all_file_groups():
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM file_groups ORDER BY id DESC")
        groups = cur.fetchall()
        
        result = []
        for g in groups:
            group_id = g[0]
            group_name = g[1]
            cur.execute("""
                SELECT d.id, d.filename 
                FROM documents d
                JOIN file_group_documents fgd ON d.id = fgd.document_id
                WHERE fgd.group_id = %s
            """, (group_id,))
            docs = cur.fetchall()
            documents = [{"id": d[0], "filename": d[1]} for d in docs]
            result.append({"id": group_id, "name": group_name, "documents": documents})
            
        cur.close()
        conn.close()
        return {"file_groups": result}
    except Exception as e:
        print(f"Error fetching file groups: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch file groups")

@router.post("/file-groups")
async def create_file_group(group: FileGroupCreate):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("INSERT INTO file_groups (name) VALUES (%s) RETURNING id", (group.name,))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"id": new_id, "name": group.name, "documents": []}
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=400, detail="Group with this name already exists")
    except Exception as e:
        print(f"Error creating file group: {e}")
        raise HTTPException(status_code=500, detail="Failed to create file group")

@router.delete("/file-groups/{group_id}")
async def delete_file_group(group_id: int):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("DELETE FROM file_groups WHERE id = %s RETURNING id", (group_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="File group not found")
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": "File group deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting file group: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file group")

@router.post("/file-groups/{group_id}/documents")
async def add_document_to_group(group_id: int, payload: FileGroupAddDocument):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        # Verify document exists
        cur.execute("SELECT id FROM documents WHERE id = %s", (payload.document_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")
            
        cur.execute("INSERT INTO file_group_documents (group_id, document_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (group_id, payload.document_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": "Document added to group"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding document to group: {e}")
        raise HTTPException(status_code=500, detail="Failed to add document to group")

@router.delete("/file-groups/{group_id}/documents/{document_id}")
async def remove_document_from_group(group_id: int, document_id: int):
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("DELETE FROM file_group_documents WHERE group_id = %s AND document_id = %s RETURNING group_id", (group_id, document_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Document not found in group")
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": "Document removed from group"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error removing document from group: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove document from group")
