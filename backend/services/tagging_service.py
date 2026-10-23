import logging
from typing import Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)

# Cap on text sent to the LLM for whole-document metadata
DOC_METADATA_CHARS = 20000


class DocumentMetadata(BaseModel):
    year: str = Field(description="The year mentioned or implied in the text")
    grade: str = Field(description="The grade level suitable for the text")
    subject: str = Field(description="The main subject of the text")
    topic: str = Field(description="The main topic of the text")
    subtopic: str = Field(description="The subtopic of the text")


class ChunkTags(BaseModel):
    tags: list[str] = Field(description="Exactly 10 descriptive tags for the text", min_length=10, max_length=10)


class ChunkSummary(BaseModel):
    summary: str = Field(description="A concise 2-3 sentence summary of the text")


_llm = ChatOpenAI(
    model=settings.TAGGING_MODEL,
    api_key="ollama",  # Ollama ignores the key but the client requires one
    base_url=settings.TAGGING_BASE_URL,
    temperature=0.0,
    reasoning_effort="none",  # Qwen3 thinking adds latency and nothing to tags
)


def _chain(schema: type[BaseModel], instruction: str):
    parser = JsonOutputParser(pydantic_object=schema)
    prompt = PromptTemplate(
        template=instruction + "\n{format_instructions}\n\nText:\n{text}",
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    # Constrained decoding: small local models otherwise echo the schema back instead of filling it
    llm = _llm.bind(response_format={"type": "json_schema",
                                     "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}})
    return prompt | llm | parser


_document_chain = _chain(DocumentMetadata, "Given the following document, generate its metadata.")
_chunk_chain = _chain(ChunkTags, "Given the following text chunk, generate descriptive tags.")
_summary_chain = _chain(ChunkSummary, "Given the following text chunk, summarize it.")


def _run(chain, texts: list[str]) -> list[Optional[dict]]:
    """Run a chain over each text concurrently; None where generation fails."""
    results = chain.batch(
        [{"text": t} for t in texts],
        config={"max_concurrency": 2},  # local Ollama queues beyond this; more only costs RAM
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Metadata generation failed: %s", r)
    return [None if isinstance(r, Exception) else r for r in results]


@traceable
def generate_document_metadata(text: str) -> Optional[dict]:
    """Year, grade, subject, topic and subtopic for a whole document; None on failure."""
    return _run(_document_chain, [text[:DOC_METADATA_CHARS]])[0]


@traceable
def generate_chunk_tags(texts: list[str]) -> list[Optional[list[str]]]:
    """Tags for each chunk; None where generation fails."""
    return [r["tags"] if r else None for r in _run(_chunk_chain, texts)]


@traceable
def generate_chunk_summaries(texts: list[str]) -> list[Optional[str]]:
    """Summary of each chunk; None where generation fails."""
    return [r["summary"] if r else None for r in _run(_summary_chain, texts)]
