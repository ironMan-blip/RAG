from pydantic import BaseModel
from typing import Optional



class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
