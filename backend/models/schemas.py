from typing import Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    sender: str
    text: str
    prompt: Optional[str] = None  # bot turns only: the full prompt the LLM received
    timings: Optional[list[dict]] = None  # bot turns only: [{"step", "ms"}] in pipeline order


class ChatResponse(BaseModel):
    session_id: str
    # The user turn as stored by the backend plus the bot reply, ready to display
    messages: list[ChatMessage]


class NewChatResponse(BaseModel):
    session_id: str
    history: list[ChatMessage]
