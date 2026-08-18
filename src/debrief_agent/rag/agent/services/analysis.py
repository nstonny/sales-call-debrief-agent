from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from typing import Any, cast

from fastapi import HTTPException
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from openai import OpenAIError
from pydantic import ValidationError

from debrief_agent.core.observability import (
    get_current_trace_id,
    observe,
    update_current_span_metadata,
)
from debrief_agent.rag.agent.prompts.analysis import (
    build_analysis_system_prompt,
    build_analysis_user_message,
)
from debrief_agent.rag.agent.tools import (
    retrieve_call_examples,
    retrieve_coaching_guides,
    retrieve_sales_frameworks,
)
from debrief_agent.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)

# Pairs with DEFAULT_MODEL_NAME in services/extraction.py. This one drives the
# tool-calling debrief agent, so it defaults to a stronger model.
DEFAULT_MODEL_NAME = os.getenv("DEBRIEF_ANALYSIS_MODEL", "gpt-5-mini")

SYSTEM_PROMPT = build_analysis_system_prompt()


class CallAnalyzer:
    """LangChain-based debrief analyzer that uses retrieval tools."""

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.0,
        tools: Iterable[Any] | None = None,
    ) -> None:
        self._model_name = model_name or DEFAULT_MODEL_NAME
        self._temperature = temperature
        self._tools = list(
            tools
            if tools is not None
            else [
                retrieve_sales_frameworks,
                retrieve_coaching_guides,
                retrieve_call_examples,
            ]
        )

        self._model = ChatOpenAI(
            model=self._model_name,
            temperature=self._temperature,
        )
        self._agent = create_agent(
            model=self._model,
            tools=self._tools,
            system_prompt=SYSTEM_PROMPT,
        )

    @observe(name="analysis.generate", as_type="span", capture_input=False, capture_output=False)
    async def analyze(
        self,
        transcript: str,
        metadata: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a structured debrief using tool-backed retrieval context."""
        cleaned_transcript = transcript.strip()
        if not cleaned_transcript:
            raise HTTPException(status_code=422, detail="Transcript must not be empty")

        trace_id = get_current_trace_id()
        trace_metadata: dict[str, Any] = {
            "service": "analysis",
            "model": self._model_name,
            "trace_id": trace_id,
            "session_id": session_id,
            "had_refusal": False,
            "validation_ok": False,
            "error_type": "none",
        }
        update_current_span_metadata(trace_metadata)

        try:
            request_payload = cast(
                Any,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": build_analysis_user_message(cleaned_transcript, metadata),
                        }
                    ]
                },
            )

            result = await self._agent.ainvoke(request_payload)

            from langchain_core.messages import AIMessage
            from langfuse import get_client

            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage):
                    usage = getattr(msg, "usage_metadata", None)
                    if usage:
                        get_client().update_current_generation(
                            model=self._model_name,
                            usage_details={
                                "input": usage.get("input_tokens", 0),
                                "output": usage.get("output_tokens", 0),  # confirmed 2379
                                "total": usage.get("total_tokens", 0),
                            },
                        )
                    break
        except OpenAIError as exc:
            trace_metadata["error_type"] = "openai_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "OpenAI API call failed during debrief generation (trace_id=%s): %s",
                trace_id,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM debrief failed -- OpenAI API error: {exc}",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            trace_metadata["error_type"] = "agent_error"
            update_current_span_metadata(trace_metadata)
            logger.exception(
                "LangChain agent execution failed during debrief generation (trace_id=%s)",
                trace_id,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM debrief failed -- agent execution error: {exc}",
            ) from exc

        try:
            raw_payload = self._extract_agent_payload(result)
            if isinstance(raw_payload, AnalysisResult):
                analysis = raw_payload
            else:
                analysis = AnalysisResult.model_validate(self._load_payload(raw_payload))
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            trace_metadata["validation_ok"] = False
            trace_metadata["error_type"] = "validation_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "LLM debrief response failed schema validation (trace_id=%s). Parsed payload: %r -- Errors: %s",
                trace_id,
                result,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail="LLM debrief failed -- response did not match expected schema.",
            ) from exc

        trace_metadata["validation_ok"] = True
        update_current_span_metadata(trace_metadata)
        return analysis.model_dump()

    @staticmethod
    def _extract_agent_payload(result: dict[str, Any]) -> Any:
        """Return the most useful payload emitted by the LangChain agent."""
        for key in ("structured_response", "output_parsed", "output", "final"):
            if key in result and result[key] is not None:
                return result[key]

        messages = result.get("messages", [])
        if not messages:
            return ""

        last_message = messages[-1]
        content = getattr(last_message, "content", None)
        if content is None and isinstance(last_message, dict):
            content = last_message.get("content")
        return content or ""

    @staticmethod
    def _load_payload(payload: Any) -> Any:
        """Normalize agent output into a JSON-compatible object."""
        if isinstance(payload, dict):
            return CallAnalyzer._coerce_payload_shape(payload)
        if isinstance(payload, AnalysisResult):
            return payload.model_dump()
        if isinstance(payload, list):
            text_parts: list[str] = []
            for item in payload:
                text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            payload = "\n".join(text_parts)

        if isinstance(payload, str):
            cleaned = CallAnalyzer._strip_code_fences(payload.strip())
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return CallAnalyzer._coerce_payload_shape(parsed)
            return parsed

        raise ValueError("Agent did not return a JSON-compatible payload")

    @staticmethod
    def _coerce_payload_shape(payload: dict[str, Any]) -> dict[str, Any]:
        """Coerce known model drifts into schema-compatible shapes."""
        coerced = dict(payload)
        competitor = coerced.get("competitor_mentioned")
        next_steps = coerced.get("next_steps")

        if isinstance(competitor, list):
            parts: list[str] = []
            for item in competitor:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                elif isinstance(item, dict):
                    # Support object-shaped competitors by extracting common labels.
                    for key in ("name", "competitor", "value"):
                        value = item.get(key)
                        if isinstance(value, str) and value.strip():
                            parts.append(value.strip())
                            break

            coerced["competitor_mentioned"] = "; ".join(parts) if parts else None

        if isinstance(next_steps, list):
            parts: list[str] = []
            for item in next_steps:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                elif isinstance(item, dict):
                    segments: list[str] = []
                    for key in ("action", "owner", "due", "goal"):
                        value = item.get(key)
                        if isinstance(value, str) and value.strip():
                            segments.append(value.strip())
                    if segments:
                        parts.append(" | ".join(segments))

            coerced["next_steps"] = "; ".join(parts)

        return coerced

    @staticmethod
    def _strip_code_fences(value: str) -> str:
        """Remove markdown fences so JSON parsing is more forgiving."""
        stripped = value.strip()
        if stripped.startswith("```"):
            stripped = stripped[3:]
            if stripped.lstrip().startswith("json"):
                stripped = stripped.lstrip()[4:]
            stripped = stripped.strip()
            if stripped.endswith("```"):
                stripped = stripped[:-3].strip()
        return stripped


_default_call_analyzer = CallAnalyzer()


async def analyze_transcript(
    transcript: str,
    metadata: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper around the default debrief analyzer."""
    return await _default_call_analyzer.analyze(
        transcript=transcript,
        metadata=metadata,
        session_id=session_id,
    )
