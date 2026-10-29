import logging
import time
from typing import Callable, Optional

import openai
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)

# Cap on text sent to the LLM for whole-document metadata
DOC_METADATA_CHARS = 20000
# A call running longer than this is treated as stuck; Ollama aborts it once the client hangs up.
# Doubles after each timeout so a merely slow call (cold model load, long document) still finishes.
LLM_TIMEOUT_SECONDS = 180
MAX_BACKOFF_SECONDS = 60


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


# Field names match DocumentMetadata so retrieval compares them key by key
class QueryProfile(BaseModel):
    year: str = Field(description="The year mentioned or implied by the question, or empty string if none")
    grade: str = Field(description="The grade level implied by the question, or empty string if none")
    subject: str = Field(description="The subject of the question, or empty string if unclear")
    topic: str = Field(description="The topic of the question, or empty string if unclear")
    subtopic: str = Field(description="The subtopic of the question, or empty string if unclear")


class ChatTitle(BaseModel):
    title: str = Field(description="A 3-5 word title for the chat, no quotes")


def _llm(temperature: float, timeout: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.TAGGING_MODEL,
        api_key="ollama",  # Ollama ignores the key but the client requires one
        base_url=settings.LLM_BASE_URL,
        temperature=temperature,
        timeout=timeout,
        max_retries=0,  # _run owns retries, so rate-limit waits and stuck detection follow one policy
        reasoning_effort="none",  # Qwen3 thinking adds latency and nothing to tags
    )


def _chain(schema: type[BaseModel], instruction: str):
    """A builder of the chain at a given temperature and timeout, so retries can change both."""
    parser = JsonOutputParser(pydantic_object=schema)
    prompt = PromptTemplate(
        template=instruction + "\n{format_instructions}\n\nText:\n{text}",
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    # Constrained decoding: small local models otherwise echo the schema back instead of filling it
    response_format = {"type": "json_schema",
                       "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}
    return lambda temperature, timeout: prompt | _llm(temperature, timeout).bind(response_format=response_format) | parser


_document_chain = _chain(DocumentMetadata, "Given the following document, generate its metadata.")
_chunk_chain = _chain(ChunkTags, "Given the following text chunk, generate descriptive tags.")
_summary_chain = _chain(ChunkSummary, "Given the following text chunk, summarize it.")
_query_chain = _chain(QueryProfile, "Given the following user question, guess its metadata.")
_title_chain = _chain(ChatTitle, "Given the following first message of a chat, write a short title for the chat.")


def _diagnose(err: Exception) -> Optional[str]:
    """What went wrong, for errors a retry can fix; None for the rest (bad key, unknown model, bad request, bugs)."""
    if isinstance(err, openai.APITimeoutError):
        return "stuck (timed out)"
    if isinstance(err, openai.APIConnectionError):
        return "LLM server unreachable"
    if isinstance(err, openai.RateLimitError):
        return "rate limited"
    if isinstance(err, openai.InternalServerError):
        return "LLM server error"
    if isinstance(err, OutputParserException):
        return "unparseable output"
    return None


def _retry_delay(err: Exception, attempt: int) -> float:
    """Seconds to wait before retrying: until a rate limit resets if the provider says when, else exponential backoff."""
    if isinstance(err, openai.RateLimitError):
        try:
            after = err.response.headers.get("retry-after")
            if after:
                return float(after)
            reset_ms = float(err.body["metadata"]["headers"]["X-RateLimit-Reset"])  # OpenRouter's reset epoch
            return max(1.0, reset_ms / 1000 - time.time())
        except (TypeError, KeyError, ValueError):
            pass
    if isinstance(err, (OutputParserException, openai.APITimeoutError)):
        return 0.0  # the fix is a higher temperature or longer timeout, and a stuck call already waited
    return min(MAX_BACKOFF_SECONDS, 2.0 ** attempt)


def _run(chain, texts: list[str], persist: bool = False,
         on_success: Optional[Callable[[int, dict], None]] = None) -> list[Optional[dict]]:
    """Run a chain over each text concurrently; None where generation fails.

    on_success(index, result) is called as each text finishes, so callers can save results before the batch ends.

    With persist, failed texts are retried until every one succeeds, adapting to the cause: a stuck call gets a
    longer timeout, unparseable output a higher temperature, a rate limit waits for its reset. Errors no retry
    can fix raise instead, so stored metadata is either complete or the upload fails loudly.
    """
    results: list = [None] * len(texts)
    pending = list(range(len(texts)))
    attempt = timeouts = bad_outputs = 0
    while pending:
        attempt += 1
        errors = {}
        # As completed, so on_success sees each result while the rest of the batch runs
        for j, r in chain(min(1.0, 0.3 * bad_outputs), LLM_TIMEOUT_SECONDS * 2 ** timeouts).batch_as_completed(
            [{"text": texts[i]} for i in pending],
            config={"max_concurrency": 2},  # local Ollama queues beyond this; more only costs RAM
            return_exceptions=True,
        ):
            if isinstance(r, Exception):
                errors[pending[j]] = r
            else:
                results[pending[j]] = r
                if on_success:
                    on_success(pending[j], r)
        pending = sorted(errors)
        for err in errors.values():
            logger.warning("Metadata generation failed (attempt %d, %s): %s", attempt, _diagnose(err) or "not retryable", err)
        if not pending or not persist:
            break

        fatal = next((e for e in errors.values() if _diagnose(e) is None), None)
        if fatal is not None:
            raise fatal
        timeouts += any(isinstance(e, openai.APITimeoutError) for e in errors.values())
        bad_outputs += any(isinstance(e, OutputParserException) for e in errors.values())
        delay = max(_retry_delay(e, attempt) for e in errors.values())
        logger.warning("Retrying %d of %d in %.0fs", len(pending), len(texts), delay)
        time.sleep(delay)
    return results


@traceable
def generate_document_metadata(text: str) -> Optional[dict]:
    """Year, grade, subject, topic and subtopic for a whole document; retries until it succeeds."""
    return _run(_document_chain, [text[:DOC_METADATA_CHARS]], persist=True)[0]


@traceable
def generate_chunk_tags(texts: list[str], on_result: Optional[Callable[[int, list[str]], None]] = None) -> list[Optional[list[str]]]:
    """Tags for each chunk; retries until every chunk succeeds. on_result(index, tags) fires as each one finishes."""
    on_success = on_result and (lambda i, r: on_result(i, r["tags"]))
    return [r["tags"] if r else None for r in _run(_chunk_chain, texts, persist=True, on_success=on_success)]


@traceable
def generate_chunk_summaries(texts: list[str], on_result: Optional[Callable[[int, str], None]] = None) -> list[Optional[str]]:
    """Summary of each chunk; retries until every chunk succeeds. on_result(index, summary) fires as each one finishes."""
    on_success = on_result and (lambda i, r: on_result(i, r["summary"]))
    return [r["summary"] if r else None for r in _run(_summary_chain, texts, persist=True, on_success=on_success)]


@traceable
def generate_query_profile(text: str) -> dict:
    """Guessed year, grade, subject, topic, subtopic for a question; {} on failure."""
    return _run(_query_chain, [text])[0] or {}


@traceable
def generate_chat_title(text: str) -> str:
    """Short chat title for a first message; the message's first 30 characters on failure."""
    r = _run(_title_chain, [text])[0]
    return r["title"].strip().strip('"') if r else (text[:30] + "..." if len(text) > 30 else text)
