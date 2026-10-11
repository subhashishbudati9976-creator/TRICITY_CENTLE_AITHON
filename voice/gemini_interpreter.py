"""Gemini-backed natural-language interpretation with strict registered actions."""

import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Optional

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field

from voice.action_registry import CAPABILITIES, PlanValidationError, validate_request
from voice.command_parser import ActionRequest
from voice.knowledge_base import GESTURES


logger = logging.getLogger(__name__)
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_TIMEOUT_SECONDS = 12.0
MAX_TIMEOUT_SECONDS = 60.0


class PlannerResponse(BaseModel):
    """One structured result from Gemini; mode-specific constraints are checked below."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["action", "answer", "none"]
    action_name: Optional[str] = None
    params: Dict[str, str | int] = Field(default_factory=dict)
    answer: Optional[str] = None


class PlannerUnavailable(RuntimeError):
    """Raised when Gemini is not configured or cannot provide a valid result."""


def validate_result(payload: Any) -> tuple[Optional[ActionRequest], str]:
    """Validate result shape and ensure an action resolves to one registered capability."""
    try:
        result = PlannerResponse.model_validate(payload)
    except Exception as exc:
        raise PlanValidationError("Gemini returned a malformed response") from exc

    if result.kind == "action":
        if not result.action_name or result.answer is not None:
            raise PlanValidationError("Action result must contain only an action and parameters")
        try:
            domain, intent = result.action_name.split(".", maxsplit=1)
        except ValueError as exc:
            raise PlanValidationError("Action name must be a registered DOMAIN.INTENT") from exc
        request = ActionRequest(
            domain=domain.upper(),
            intent=intent.upper(),
            params=result.params,
            raw_segment="Gemini action",
        )
        try:
            validate_request(request)
        except PlanValidationError as val_err:
            if "Missing parameters" in str(val_err) and intent.upper() in ("LAUNCH_APP", "CLOSE_APP"):
                action_word = "open" if intent.upper() == "LAUNCH_APP" else "close"
                return None, f"Which application would you like me to {action_word}?"
            raise
        return request, ""

    if result.action_name is not None or result.params:
        raise PlanValidationError("Answer and none results cannot include action parameters")
    if result.kind == "answer":
        if not result.answer or not result.answer.strip() or len(result.answer) > 4000:
            raise PlanValidationError("Answer result must contain text up to 4000 characters")
        return None, result.answer.strip()

    answer = (result.answer or "").strip()
    if len(answer) > 4000:
        raise PlanValidationError("None response text exceeds the size limit")
    return None, answer


def _clean_schema(schema: Any) -> Any:
    """Recursively strip fields unsupported by Gemini Developer API mode.
    Specifically removes 'additionalProperties' which triggers SDK ValueError."""
    if isinstance(schema, dict):
        return {
            k: _clean_schema(v)
            for k, v in schema.items()
            if k != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_clean_schema(item) for item in schema]
    return schema


def _response_schema() -> Dict[str, Any]:
    """Build an SDK JSON schema with action names restricted to registered actions."""
    schema = PlannerResponse.model_json_schema()
    action_name_schema = schema["properties"]["action_name"]
    nullable_schemas = action_name_schema.get("anyOf", [])
    string_schema = next(
        (item for item in nullable_schemas if item.get("type") == "string"),
        action_name_schema,
    )
    string_schema["enum"] = [
        f"{domain}.{intent}" for domain, intent in CAPABILITIES
    ]
    schema["properties"]["params"] = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Target application name to launch or close, e.g. notepad, chrome, calculator"},
            "query": {"type": "string", "description": "Search query or file search term"},
            "url": {"type": "string", "description": "Web URL to navigate to"},
            "site_key": {"type": "string", "description": "Known destination website key, e.g. youtube, google, github"},
            "folder_key": {"type": "string", "description": "Known user folder key, e.g. documents, downloads, desktop"},
            "filename": {"type": "string", "description": "Specific filename to open"},
            "text": {"type": "string", "description": "Text to type into active input"},
            "dx": {"type": "integer", "description": "Horizontal cursor movement delta"},
            "dy": {"type": "integer", "description": "Vertical cursor movement delta"},
        },
    }
    return _clean_schema(schema)


def _strip_markdown_code_fence(text: str) -> str:
    """Strip markdown code fence wrappers (```json ... ``` or ``` ... ```) and whitespace."""
    trimmed = text.strip()
    if trimmed.startswith("```"):
        lines = trimmed.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        trimmed = re.sub(r"^```(?:json)?\s*", "", trimmed, flags=re.IGNORECASE)
        trimmed = re.sub(r"\s*```$", "", trimmed)
    return trimmed.strip()


def _friendly_api_error(exc: Exception) -> tuple[str, Optional[int]]:
    """Convert SDK exception metadata to a concise message without echoing exception text."""
    status = getattr(exc, "code", None)
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    name = type(exc).__name__.casefold()
    message = str(getattr(exc, "message", str(exc))).casefold()

    if status == 404 or "not_found" in name or ("model" in message and "not found" in message):
        return "The configured Gemini model was not found. AirControl will not switch models.", 404
    if status == 429 or "resource_exhausted" in name or "rate" in message or "quota" in message:
        return "Gemini is rate-limited or the API quota is exhausted. Try again later or check Google AI Studio.", 429
    if status in (401, 403) or "permission" in name or "unauthorized" in name or "api_key" in message:
        return "Gemini rejected the API credentials or access. Check the key in your .env file.", status or 401
    if "timeout" in name or isinstance(exc, TimeoutError) or "deadline" in name:
        return "Gemini did not respond before the timeout. Try again.", status
    if status is not None and status >= 500:
        return "Gemini is temporarily unavailable. Try again later.", status
    return "Gemini could not process the request. Check your connection and API configuration.", status


class GeminiInterpreter:
    """Interpret unregistered speech as an answer or a single allowlisted action."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: Any = None,
    ):
        if not api_key.strip():
            raise PlannerUnavailable("Gemini API key is not configured")
        timeout_seconds = float(timeout_seconds)
        if not 1.0 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError("AIRCONTROL_AI_TIMEOUT_SECONDS must be between 1 and 60")
        self.model = model.strip() or DEFAULT_MODEL
        self.timeout_seconds = timeout_seconds
        self.client = client or genai.Client(
            api_key=api_key.strip(),
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    @classmethod
    def from_environment(cls) -> Optional["GeminiInterpreter"]:
        project_root = Path(__file__).resolve().parents[1]
        load_dotenv(dotenv_path=project_root / ".env", override=False)
        api_key = os.environ.get("AIRCONTROL_AI_API_KEY", "").strip()
        if not api_key or api_key.casefold() in {
            "replace_with_your_api_key",
            "your_api_key",
        }:
            return None
        model = os.environ.get("AIRCONTROL_AI_MODEL", DEFAULT_MODEL).strip()
        timeout = os.environ.get(
            "AIRCONTROL_AI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)
        ).strip()
        try:
            return cls(api_key, model=model, timeout_seconds=float(timeout))
        except (TypeError, ValueError):
            logger.warning(
                "Gemini configuration is invalid; AI interpretation is disabled."
            )
            return None

    def interpret(
        self,
        utterance: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> tuple[Optional[ActionRequest], str, bool]:
        """Return (action, answer, confidence) without executing desktop operations."""
        catalogue = [
            {
                "action_name": f"{domain}.{intent}",
                "description": capability.description,
                "parameters": {
                    name: kind.__name__ for name, kind in capability.params.items()
                },
            }
            for (domain, intent), capability in CAPABILITIES.items()
        ]
        prompt = (
            "Interpret the user's request for AirControl, a Windows accessibility assistant. "
            "Return exactly one JSON result matching the supplied schema. "
            "Use kind=action only when the intent clearly matches one registered action. "
            "For actions requiring parameters (such as APPLICATION.LAUNCH_APP, APPLICATION.CLOSE_APP, "
            "BROWSER.SEARCH_GOOGLE, BROWSER.SEARCH_YOUTUBE, BROWSER.OPEN_DESTINATION, BROWSER.OPEN_URL, "
            "FILE_SYSTEM.OPEN_FOLDER, FILE_SYSTEM.OPEN_FILE, SYSTEM.TYPE_TEXT), you MUST extract and provide "
            "the corresponding parameter in 'params' (e.g. 'app_name': 'notepad', 'query': '...', 'site_key': 'youtube'). "
            "If the user asks an open-ended request without naming the application (e.g. 'open an app', 'launch it', 'close an app'), "
            "use kind=answer to ask which application they would like to open or close. "
            "Use kind=answer for information questions about AirControl, its capabilities, or hand gestures. "
            "Use kind=none when ambiguous, unsupported, or not confidently understood. "
            "Never invent actions, make claims that an operation succeeded, or provide shell commands, Python, PowerShell, or CMD. "
            f"Registered action catalogue: {catalogue!r}. Gesture registry: {GESTURES!r}."
        )
        contents: list[dict[str, Any]] = []
        for item in (history or [])[-6:]:
            if (
                isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}
                and isinstance(item.get("content"), str)
            ):
                contents.append(
                    {"role": item["role"], "parts": [{"text": item["content"][:1000]}]}
                )
        contents.append({"role": "user", "parts": [{"text": utterance[:2000]}]})

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=prompt,
                    response_mime_type="application/json",
                    response_schema=_response_schema(),
                    temperature=0,
                ),
            )
        except Exception as exc:
            message, status = _friendly_api_error(exc)
            if status == 404:
                available = self._available_model_names()
                if available:
                    message += " Models currently listed for this API key: " + ", ".join(available)
                else:
                    message += " The Gemini models list could not be retrieved; check Google AI Studio."
            logger.warning(
                "Gemini request failed (%s, status=%s).",
                type(exc).__name__,
                status if status is not None else "unavailable",
            )
            raise PlannerUnavailable(message) from exc

        # Inspect SDK response structure before parsing
        prompt_feedback = getattr(response, "prompt_feedback", None)
        if prompt_feedback is not None:
            block_reason = getattr(prompt_feedback, "block_reason", None)
            if block_reason:
                logger.warning("Gemini request was blocked by prompt feedback: %s", block_reason)
                raise PlannerUnavailable(f"Gemini request was blocked ({block_reason}). Please rephrase the request.")

        candidates = getattr(response, "candidates", None)
        if candidates:
            candidate = candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)
            if finish_reason is not None:
                finish_str = str(finish_reason).upper()
                if "SAFETY" in finish_str:
                    logger.warning("Gemini response candidate was blocked by safety filters.")
                    raise PlannerUnavailable("Gemini response was blocked by safety filters. Please rephrase the request.")
                if "MAX_TOKENS" in finish_str:
                    logger.warning("Gemini response candidate reached token limit.")
                    raise PlannerUnavailable("Gemini response reached token limit before completing. Please simplify the request.")
                if "RECITATION" in finish_str:
                    logger.warning("Gemini response candidate was flagged for recitation.")
                    raise PlannerUnavailable("Gemini response was flagged for recitation. Please rephrase the request.")
                if "BLOCK" in finish_str:
                    logger.warning("Gemini response candidate was blocked: %s", finish_str)
                    raise PlannerUnavailable(f"Gemini response was blocked ({finish_str}). Please rephrase the request.")

        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            payload = (
                parsed.model_dump()
                if isinstance(parsed, BaseModel)
                else parsed
            )
        else:
            text = getattr(response, "text", None)
            if text is None and candidates:
                candidate_parts = getattr(getattr(candidates[0], "content", None), "parts", None)
                if candidate_parts:
                    text_segs = [getattr(p, "text", "") for p in candidate_parts if getattr(p, "text", None)]
                    if text_segs:
                        text = "".join(text_segs)

            if not isinstance(text, str) or not text.strip():
                logger.warning("Gemini returned an empty response or missing content.")
                raise PlannerUnavailable("Gemini returned an invalid response (empty response). Please rephrase the request.")

            cleaned_text = _strip_markdown_code_fence(text)
            if not cleaned_text:
                raise PlannerUnavailable("Gemini returned an invalid response (empty content). Please rephrase the request.")

            try:
                payload = json.loads(cleaned_text)
            except json.JSONDecodeError as exc:
                excerpt = cleaned_text[:80].replace("\n", " ")
                logger.warning("Gemini response could not be parsed as JSON: %s (excerpt: %r)", exc, excerpt)
                raise PlannerUnavailable(
                    "Gemini returned an invalid response. Please rephrase the request."
                ) from exc

        try:
            action, answer = validate_result(payload)
        except PlanValidationError as exc:
            logger.warning("Gemini structured payload failed schema validation: %s", exc)
            raise PlannerUnavailable(
                f"Gemini returned an invalid response ({exc}). Please rephrase the request."
            ) from exc

        confident = not (
            isinstance(payload, dict) and payload.get("kind") == "none"
        )
        return action, answer, confident

    def _available_model_names(self) -> List[str]:
        """Query the Gemini models list after a model-not-found response only."""
        try:
            names = []
            for model in self.client.models.list():
                name = getattr(model, "name", "")
                if isinstance(name, str) and name:
                    names.append(name.removeprefix("models/"))
                if len(names) == 20:
                    break
            return names
        except Exception as exc:
            logger.warning(
                "Gemini model listing failed (%s).", type(exc).__name__
            )
            return []
