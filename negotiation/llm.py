"""LLM wrapper — OpenAI GPT-5.6 Terra with an offline mock fallback.

One entry point, `complete_json`, returns a parsed JSON object. If OPENAI_API_KEY
is missing OR the API call fails mid-demo, it falls back to a caller-supplied mock
so the demo never hard-crashes on stage.

Model ID and key come from the environment (.env, gitignored):
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-5.6-terra   # optional override; note bare 'gpt-5.6' routes to Sol
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()

# gpt-5.6-terra: balanced GPT-5.6 model. The bare 'gpt-5.6' alias routes to Sol,
# so the full '-terra' suffix is required. Verified against OpenAI API docs.
DEFAULT_MODEL = "gpt-5.6-terra"
MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

_client = None
_warned = False


def _client_or_none():
    """Return a cached OpenAI client, or None if no key is configured."""
    global _client
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=key)
    return _client


def _warn_once(msg: str) -> None:
    global _warned
    if not _warned:
        print(f"[llm] {msg} — using offline mock.", file=sys.stderr)
        _warned = True


def using_live_model() -> bool:
    """True if a real API key is present (demo will call OpenAI)."""
    return _client_or_none() is not None


def complete_json(
    system: str,
    user: str,
    mock: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Return (parsed_json, source). source is 'openai' or 'mock'.

    `mock` is a zero-arg callable that produces a valid response dict; it is used
    when there is no API key or the call fails. Reasoning-model-safe: no temperature
    or token cap is sent (GPT-5.6 reasoning models reject some sampling params).
    """
    client = _client_or_none()
    if client is None:
        _warn_once("no OPENAI_API_KEY")
        return mock(), "mock"
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content), "openai"
    except Exception as e:  # network, auth, rate limit, bad JSON — never crash the demo
        _warn_once(f"API error: {type(e).__name__}: {e}")
        return mock(), "mock"
