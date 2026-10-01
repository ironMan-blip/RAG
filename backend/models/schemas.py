from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    attached_filename: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
