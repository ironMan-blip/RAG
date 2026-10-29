from typing import Optional

from pydantic import BaseModel, computed_field


class ChatMessage(BaseModel):
    sender: str
    text: str
    prompt: Optional[str] = None  # bot turns only: the full prompt the LLM received
    timings: Optional[list[dict]] = None  # bot turns only: [{"step", "ms"}] in pipeline order

    @computed_field
    @property
    def total_ms(self) -> Optional[int]:
        return sum(t["ms"] for t in self.timings) if self.timings else None


class ChatResponse(BaseModel):
    session_id: str
    # The user turn as stored by the backend plus the bot reply, ready to display
    messages: list[ChatMessage]


class NewChatResponse(BaseModel):
    session_id: str
    history: list[ChatMessage]
