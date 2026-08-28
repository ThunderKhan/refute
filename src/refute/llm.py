from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class LLMError(RuntimeError):
    """Raised when a configured language-model provider cannot return a response."""


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return a text completion for the supplied messages."""


@dataclass(frozen=True, slots=True)
class OllamaLLM:
    model: str
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 120.0

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0},
        }
        response = _post_json(
            f"{self.base_url.rstrip('/')}/api/chat",
            payload,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            return str(response["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise LLMError("Ollama returned an unexpected response shape") from exc


@dataclass(frozen=True, slots=True)
class OpenAICompatibleLLM:
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 120.0

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        response = _post_json(
            f"{self.base_url.rstrip('/')}/chat/completions",
            payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=self.timeout_seconds,
        )
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("provider returned an unexpected OpenAI-compatible response") from exc


def provider_from_env(provider: str, model: str | None = None) -> LLM:
    if provider == "ollama":
        resolved_model = model or os.getenv("REFUTE_MODEL")
        if not resolved_model:
            raise LLMError("set --model or REFUTE_MODEL for the Ollama baseline")
        return OllamaLLM(
            model=resolved_model,
            base_url=os.getenv("REFUTE_OLLAMA_URL", "http://127.0.0.1:11434"),
        )

    if provider == "openai-compatible":
        resolved_model = model or os.getenv("REFUTE_MODEL")
        base_url = os.getenv("REFUTE_API_BASE")
        api_key = os.getenv("REFUTE_API_KEY")
        missing = [
            name
            for name, value in (
                ("REFUTE_MODEL/--model", resolved_model),
                ("REFUTE_API_BASE", base_url),
                ("REFUTE_API_KEY", api_key),
            )
            if not value
        ]
        if missing:
            raise LLMError("missing configuration: " + ", ".join(missing))
        return OpenAICompatibleLLM(
            model=resolved_model,
            base_url=base_url,
            api_key=api_key,
        )

    raise LLMError(f"unsupported provider: {provider}")


def _post_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float,
) -> dict:
    encoded = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=encoded, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"provider returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMError(f"could not reach language-model provider: {exc}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LLMError("provider returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMError("provider returned a non-object JSON response")
    return parsed
