import os
import psycopg2
from psycopg2 import sql
from core.config import settings

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database")

def extract_text_from_file(file_path, filename):
    extracted_text = ""
    try:
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            if TESSERACT_AVAILABLE:
                image = Image.open(file_path)
                extracted_text = pytesseract.image_to_string(image)
            else:
                extracted_text = "[Tesseract not available to read image]"
        elif filename.lower().endswith('.pdf'):
            if PYPDF_AVAILABLE:
                pdf_reader = pypdf.PdfReader(file_path)
                for page in pdf_reader.pages:
                    extracted_text += (page.extract_text() or "") + "\n"
            else:
                extracted_text = "[pypdf not available to read PDF]"
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                extracted_text = f.read()
    except Exception as e:
        extracted_text = f"[Error reading file: {e}]"
    return extracted_text

def init_db():
    print(f"Connecting to {settings.DATABASE_URL}...")
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        
        # Create table if it doesn't exist
        cur.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) UNIQUE NOT NULL,
                content TEXT NOT NULL,
                file_hash VARCHAR(255),
                file_url TEXT
            )
        ''')
        
        # Load existing files from the 'database' folder
        if os.path.exists(DATABASE_DIR):
            for filename in os.listdir(DATABASE_DIR):
                file_path = os.path.join(DATABASE_DIR, filename)
                if not os.path.isfile(file_path):
                    continue
                
                print(f"Processing {filename}...")
                content = extract_text_from_file(file_path, filename)
                
                # Compute hash of the file
                import hashlib
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                
                file_url = f"local://{file_path}"
                
                try:
                    cur.execute(
                        "INSERT INTO documents (filename, content, file_hash, file_url) VALUES (%s, %s, %s, %s) ON CONFLICT (filename) DO UPDATE SET content = EXCLUDED.content, file_hash = EXCLUDED.file_hash, file_url = EXCLUDED.file_url",
                        (filename, content, file_hash, file_url)
                    )
                    print(f"Inserted/Updated {filename}")
                except Exception as e:
                    print(f"Failed to insert {filename}: {e}")
                    conn.rollback()
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialization complete.")
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    init_db()
