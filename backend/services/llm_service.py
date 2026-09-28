from openai import OpenAI
from core.config import settings
import os
import io

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

DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database")

def get_database_context() -> str:
    context = ""
    if not os.path.exists(DATABASE_DIR):
        return context

    for filename in os.listdir(DATABASE_DIR):
        file_path = os.path.join(DATABASE_DIR, filename)
        if not os.path.isfile(file_path):
            continue
        
        extracted_text = f"\n--- Content of {filename} ---\n"
        
        try:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                if TESSERACT_AVAILABLE:
                    image = Image.open(file_path)
                    extracted_text += pytesseract.image_to_string(image)
                else:
                    extracted_text += "[Tesseract not available to read image]"
            elif filename.lower().endswith('.pdf'):
                if PYPDF_AVAILABLE:
                    pdf_reader = pypdf.PdfReader(file_path)
                    for page in pdf_reader.pages:
                        extracted_text += (page.extract_text() or "") + "\n"
                else:
                    extracted_text += "[pypdf not available to read PDF]"
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    extracted_text += f.read()
        except Exception as e:
            extracted_text += f"[Error reading file: {e}]"
            
        context += extracted_text + "\n"
        
    return context

# Initialize the OpenAI client pointing to OpenRouter
client = OpenAI(
  base_url=settings.OPENROUTER_BASE_URL,
  api_key=settings.OPENROUTER_API_KEY,
)

def get_chat_completion(message: str) -> str:
    """Sends a message to the AI and retrieves the reply, including database context."""
    db_context = get_database_context()
    
    system_prompt = "You are a very helpful AI assistant. Use the provided database context to answer the user's query."
    if db_context:
        system_prompt += f"\n\nDATABASE CONTEXT:\n{db_context}"

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": message
            }
        ],
        extra_body={"reasoning": {"enabled": True}}
    )
    
    return response.choices[0].message.content
