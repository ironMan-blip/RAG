from pydantic import BaseModel
from typing import List, Optional


class ChatMessage(BaseModel):
    sender: str
    text: str


class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
    # The user turn as stored by the backend plus the bot reply, ready to display
    messages: List[ChatMessage] = []


class NewChatResponse(BaseModel):
    session_id: str
    history: List[ChatMessage]
