import logging
from typing import Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)


class TagMetadata(BaseModel):
    year: str = Field(description="The year mentioned or implied in the text")
    grade: str = Field(description="The grade level suitable for the text")
    subject: str = Field(description="The main subject of the text")
    topic: str = Field(description="The main topic of the text")
    subtopic: str = Field(description="The subtopic of the text")
    tags: list[str] = Field(description="Exactly 10 descriptive tags for the text", min_length=10, max_length=10)


_parser = JsonOutputParser(pydantic_object=TagMetadata)
_chain = (
    PromptTemplate(
        template="Given the following text chunk, generate descriptive tags and metadata.\n{format_instructions}\n\nText:\n{chunk_text}",
        input_variables=["chunk_text"],
        partial_variables={"format_instructions": _parser.get_format_instructions()},
    )
    | ChatOpenAI(
        model=settings.LLM_MODEL2,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0.0,
    )
    | _parser
)


@traceable
def generate_metadata(texts: list[str]) -> list[Optional[dict]]:
    """Tag each text concurrently; None where generation fails."""
    results = _chain.batch(
        [{"chunk_text": t} for t in texts],
        config={"max_concurrency": 8},
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Metadata generation failed: %s", r)
    return [None if isinstance(r, Exception) else r for r in results]
