"""
services/rerank.py

Reranks retrieved RAG chunks by relevance to the query, using the OpenAI
Responses API as an LLM-as-reranker (no dedicated rerank API/vendor).

Uses the OpenAI Responses API structured parser (`client.responses.parse`).
Uses Pydantic (`RerankResult`) directly as the response format model.

Primary API:
  - `ChunkReranker.rerank(...)` is the class-based entrypoint.

Sync, not async: unlike `services/extraction.py` (called from the async
`CallAnalyzer.analyze()`), this is called from `rag/agent/tools.py`, which is
entirely synchronous -- LangChain runs those `@tool` functions from the async
agent loop via a thread-pool executor. Using an async client here would be an
inconsistent outlier in that call chain.

Behaviour on failure:
  - If the OpenAI call fails, the LLM refuses, or the response fails Pydantic
    validation: log a warning and fall back to `chunks[:top_n]` (the
    un-reranked hybrid order) rather than raising. Reranking only refines an
    already-valid candidate set, so a transient LLM hiccup here should not
    fail the whole debrief analysis the way a retrieval failure would.

Langfuse metadata (current span):
- service: "rerank"
- model: str (DEBRIEF_RERANK_MODEL, default "gpt-4.1-mini")
- trace_id: str | None
- candidate_count: int
- top_n: int
- error_type: "none" | "openai_error" | "llm_refusal" | "validation_error"
"""

import logging
import os
from typing import Any, cast

from langfuse.openai import OpenAI
from openai import OpenAIError
from pydantic import ValidationError

from debrief_agent.core.config import OPENAI_API_KEY
from debrief_agent.core.observability import (
    get_current_trace_id,
    observe,
    update_current_span_metadata,
)
from debrief_agent.rag.agent.prompts.rerank import (
    RERANK_SYSTEM_PROMPT,
    build_rerank_user_message,
)
from debrief_agent.rag.retrieval.retrieval_models import RetrievedChunk
from debrief_agent.schemas.rerank import RerankResult

logger = logging.getLogger(__name__)

# Reranking is a single structured parse over already-retrieved candidates,
# so it defaults to the same cheap, fast model as extraction.
DEFAULT_MODEL_NAME = os.getenv("DEBRIEF_RERANK_MODEL", "gpt-4.1-mini")

# Reusable sync client — one instance for the lifetime of the process.
_client = OpenAI(api_key=OPENAI_API_KEY)


class ChunkReranker:
    """Service class that reorders retrieved chunks by LLM-judged relevance."""

    def __init__(
        self,
        client: OpenAI | None = None,
        model_name: str | None = None,
    ) -> None:
        self._client = client or _client
        self._model_name = model_name or DEFAULT_MODEL_NAME

    @observe(name="rerank.rerank", as_type="span", capture_input=False, capture_output=False)
    def rerank(self, query: str, chunks: list[RetrievedChunk], top_n: int) -> list[RetrievedChunk]:
        """Return up to `top_n` chunks from `chunks`, reordered by relevance to `query`.

        Falls back to `chunks[:top_n]` (unreordered) on any LLM failure.
        """
        if len(chunks) <= 1:
            return chunks[:top_n]

        trace_id = get_current_trace_id()
        trace_metadata: dict[str, Any] = {
            "service": "rerank",
            "model": self._model_name,
            "trace_id": trace_id,
            "candidate_count": len(chunks),
            "top_n": top_n,
            "error_type": "none",
        }
        update_current_span_metadata(trace_metadata)

        # --- Call the LLM via Responses API with structured Pydantic parsing ---
        try:
            response = cast(Any, self._client.responses).parse(
                model=self._model_name,
                instructions=RERANK_SYSTEM_PROMPT,
                input=build_rerank_user_message(
                    query=query,
                    candidates=[chunk.text for chunk in chunks],
                    top_n=top_n,
                ),
                temperature=0,  # deterministic — ranking should not be creative
                text_format=RerankResult,
            )
        except OpenAIError as exc:
            trace_metadata["error_type"] = "openai_error"
            update_current_span_metadata(trace_metadata)
            logger.warning(
                "OpenAI API call failed during reranking (trace_id=%s): %s — falling back to "
                "unranked hybrid order",
                trace_id,
                exc,
            )
            return chunks[:top_n]

        # --- Check for LLM refusal before parsing ---
        refusal_part = next(
            (
                content_part
                for item in (response.output or [])
                for content_part in (getattr(item, "content", None) or [])
                if getattr(content_part, "type", None) == "refusal"
            ),
            None,
        )

        if refusal_part:
            trace_metadata["error_type"] = "llm_refusal"
            update_current_span_metadata(trace_metadata)
            refusal_text = getattr(refusal_part, "refusal", "No reason given.")
            logger.warning(
                "LLM refused reranking request (trace_id=%s). Reason: %s — falling back to "
                "unranked hybrid order",
                trace_id,
                refusal_text,
            )
            return chunks[:top_n]

        # --- Read parsed model and validate fallback payloads when needed ---
        try:
            parsed_payload = getattr(response, "output_parsed", None)
            if parsed_payload is None:
                parsed_payload = next(
                    (
                        getattr(content_part, "parsed", None)
                        for item in (response.output or [])
                        for content_part in (getattr(item, "content", None) or [])
                        if getattr(content_part, "type", None) in {"output_text", "text"}
                    ),
                    None,
                )

            if parsed_payload is None:
                raise ValueError("No parsed payload returned by Responses API")

            result = (
                parsed_payload
                if isinstance(parsed_payload, RerankResult)
                else RerankResult.model_validate(parsed_payload)
            )
        except (ValidationError, ValueError, TypeError) as exc:
            trace_metadata["error_type"] = "validation_error"
            update_current_span_metadata(trace_metadata)
            logger.warning(
                "LLM rerank response failed Pydantic validation (trace_id=%s): %s — falling "
                "back to unranked hybrid order",
                trace_id,
                exc,
            )
            return chunks[:top_n]

        update_current_span_metadata(trace_metadata)
        return self._resolve_chunks(chunks, result, top_n)

    @staticmethod
    def _resolve_chunks(
        chunks: list[RetrievedChunk],
        result: RerankResult,
        top_n: int,
    ) -> list[RetrievedChunk]:
        """Map ranked indices back to chunks, dropping out-of-range/duplicate indices."""
        seen: set[int] = set()
        resolved: list[RetrievedChunk] = []
        for ref in result.rankings:
            if ref.index in seen or not (0 <= ref.index < len(chunks)):
                continue
            seen.add(ref.index)
            chunk = chunks[ref.index]
            resolved.append(
                chunk.model_copy(
                    update={
                        "score": ref.relevance_score,
                        "metadata": {**chunk.metadata, "fusion_score": chunk.score},
                    }
                )
            )
            if len(resolved) >= top_n:
                break
        return resolved


chunk_reranker = ChunkReranker()
