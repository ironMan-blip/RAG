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
        
        for existing_filename in os.listdir("uploads"):
            existing_path = os.path.join("uploads", existing_filename)
            if os.path.isfile(existing_path):
                with open(existing_path, "rb") as f:
                    if hashlib.sha256(f.read()).hexdigest() == file_hash:
                        file_exists = True
                        break
        
        file_path = f"uploads/{file.filename}"
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
                    "INSERT INTO documents (filename, content) VALUES (%s, %s) ON CONFLICT (filename) DO UPDATE SET content = EXCLUDED.content",
                    (file.filename, extracted_text.strip())
                )
                conn.commit()
                cur.close()
                conn.close()
                upload_message += " and saved to database"
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
