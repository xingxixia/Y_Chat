from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .services.model_provider_cadence import begin_provider_call, finish_provider_call


class ProviderCallError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, error_type: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


def chat_completions_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ProviderCallError("provider base_url is empty", error_type="config")
    path = urlparse(normalized).path.rstrip("/")
    if path.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _safe_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        return 45
    return max(5, min(timeout, 120))


def _safe_max_tokens(value: Any) -> int:
    try:
        max_tokens = int(value)
    except (TypeError, ValueError):
        return 1200
    return max(128, min(max_tokens, 8192))


def build_chat_completion_body(
    config: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    json_mode: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "stream": False,
        "max_tokens": _safe_max_tokens(config.get("max_tokens", 1200)),
    }
    if config.get("temperature") is not None:
        body["temperature"] = config["temperature"]
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    provider = str(config.get("provider", ""))
    thinking_type = str(config.get("thinking_type", "disabled")).strip() or "disabled"
    if provider == "deepseek" and thinking_type in {"enabled", "disabled"}:
        body["thinking"] = {"type": thinking_type}
        reasoning_effort = str(config.get("reasoning_effort", "")).strip()
        if thinking_type == "enabled" and reasoning_effort in {"high", "max"}:
            body["reasoning_effort"] = reasoning_effort
    return body


def extract_message_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderCallError("provider response missing choices[0].message.content", error_type="response") from exc
    return str(content or "")


def post_chat_completion(
    config: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    json_mode: bool = True,
) -> dict[str, Any]:
    url = chat_completions_url(str(config.get("base_url", "")))
    body = build_chat_completion_body(config, messages, json_mode=json_mode)
    cadence_token = begin_provider_call(config)
    if not cadence_token["allowed"]:
        raise ProviderCallError(
            str(cadence_token["message"]),
            error_type="rate_limited",
        )
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )
    started_at = time.perf_counter()
    try:
        with urlopen(request, timeout=_safe_timeout(config.get("timeout_seconds", 45))) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            finish_provider_call(cadence_token, ok=True, elapsed_ms=elapsed_ms)
            return {
                "payload": payload,
                "elapsed_ms": elapsed_ms,
                "status_code": response.status,
                "url": url,
                "request_body": {key: value for key, value in body.items() if key != "messages"},
            }
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        finish_provider_call(cadence_token, ok=False, elapsed_ms=elapsed_ms, error_type="http")
        raise ProviderCallError(
            f"provider HTTP error {exc.code}: {detail}",
            status_code=exc.code,
            error_type="http",
        ) from exc
    except URLError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        finish_provider_call(cadence_token, ok=False, elapsed_ms=elapsed_ms, error_type="network")
        raise ProviderCallError(str(exc.reason), error_type="network") from exc
    except TimeoutError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        finish_provider_call(cadence_token, ok=False, elapsed_ms=elapsed_ms, error_type="timeout")
        raise ProviderCallError("provider request timed out", error_type="timeout") from exc
    except json.JSONDecodeError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        finish_provider_call(cadence_token, ok=False, elapsed_ms=elapsed_ms, error_type="response")
        raise ProviderCallError("provider returned non-JSON response", error_type="response") from exc
    except Exception:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        finish_provider_call(cadence_token, ok=False, elapsed_ms=elapsed_ms, error_type="unexpected")
        raise
