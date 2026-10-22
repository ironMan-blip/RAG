from pydantic import BaseModel
from typing import List


class ChatMessage(BaseModel):
    sender: str
    text: str


class ChatResponse(BaseModel):
    session_id: str
    # The user turn as stored by the backend plus the bot reply, ready to display
    messages: List[ChatMessage] = []


class NewChatResponse(BaseModel):
    session_id: str
    history: List[ChatMessage]
