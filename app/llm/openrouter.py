"""Thin OpenAI-compatible client for OpenRouter (RFC-0002).

Kept dependency-free: uses urllib so the core package needs no HTTP library.
The client only knows how to send a chat request and return parsed JSON; all
prompt/verdict logic lives in ``app.verification``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.config import Settings, get_settings


class LLMUnavailable(RuntimeError):
    """Raised when no API key is configured or the provider call fails."""


def _extract_json(content: str) -> dict:
    """Best-effort JSON extraction from a model response.

    Models sometimes wrap JSON in prose or markdown fences; we slice from the
    first '{' to the last '}' and parse. Callers validate the shape via Pydantic.
    """
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMUnavailable("model response contained no JSON object")
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"could not parse JSON from model response: {exc}") from exc


class OpenRouterClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def chat_json(
        self,
        model: str,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> dict:
        if not self.enabled:
            raise LLMUnavailable("OpenRouter API key is not configured")

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            url=f"{self.settings.openrouter_base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMUnavailable(f"OpenRouter request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable(f"unexpected OpenRouter response shape: {exc}") from exc

        return _extract_json(content)


def chat_json(model: str, system: str, user: str, **kwargs) -> dict:
    return OpenRouterClient().chat_json(model, system, user, **kwargs)
