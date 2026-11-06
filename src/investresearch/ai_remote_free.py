"""R-009: single-request, opt-in remote counteranalysis on PUBLIC issuer excerpts.

Model allowlists describe possible free-tier eligibility, not account billing
attestation. The operator must independently confirm Free tier / no billing.
No request is implicit, repeated, redirected, proxied, or routed to paid models.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .ai_counteranalysis import MAX_RESPONSE_BYTES, parse_response, public_prompt

# Fixed endpoints, never supplied by user/AI/model output.
ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}
SECRET_NAMES = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
# Intentionally narrow; expansion must be separately reviewed against free tier.
GEMINI_FREE_MODELS = frozenset(("gemini-2.5-flash-lite", "gemini-2.5-flash"))
GROQ_FREE_MODELS = frozenset(("llama-3.3-70b-versatile", "openai/gpt-oss-20b"))
MAX_COMPLETION_TOKENS = 800


def validate_free_model(provider: str, model: str) -> None:
    """Fail closed before reading a token or attempting a network request."""
    if provider == "gemini":
        permitted = isinstance(model, str) and model in GEMINI_FREE_MODELS
    elif provider == "groq":
        permitted = isinstance(model, str) and model in GROQ_FREE_MODELS
    elif provider == "openrouter":
        permitted = (isinstance(model, str) and
                     8 <= len(model) <= 100 and
                     model.endswith(":free") and
                     model.count(":") == 1 and
                     "/" in model and
                     all(ch.isalnum() or ch in "._/-:" for ch in model))
    else:
        raise ValueError("Only Gemini, Groq and OpenRouter have remote adapters")
    if not permitted:
        raise ValueError("Model is not approved for explicitly free-tier remote invocation")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Remote AI redirect forbidden; no token forwarding")


def _request_data(provider: str, model: str, prompt: str):
    if provider == "gemini":
        endpoint = ENDPOINTS["gemini"] + model + ":generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": MAX_COMPLETION_TOKENS,
                "temperature": 0,
            },
        }
    else:
        endpoint = ENDPOINTS[provider]
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_COMPLETION_TOKENS,
            "temperature": 0,
            "stream": False,
        }
        # Do not supply provider routing rules, fallback model arrays,
        # extra tools, web search or non-free model candidates.
    return endpoint, json.dumps(payload, ensure_ascii=False).encode("utf-8")


def invoke_free_remote(
    spec, provider, model, *, explicitly_authorized=False,
    free_tier_acknowledged=False, api_key=None
):
    """Invoke exactly ONE fixed HTTPS endpoint; return validated JSON critique.

    The free-tier assertion is an operator acknowledgement, not a billing check.
    Never print/log the raw HTTP response, bearer token, or remote exception.
    """
    if explicitly_authorized is not True or free_tier_acknowledged is not True:
        raise ValueError("Remote model requires explicit opt-in and free-tier/no-billing acknowledgement")
    validate_free_model(provider, model)
    prompt = public_prompt(spec)
    key = os.environ.get(SECRET_NAMES[provider]) if api_key is None else api_key
    if (not isinstance(key, str) or not key or len(key) > 8192 or
            any(ch in key for ch in "\r\n\x00")):
        raise ValueError("Configured remote provider secret is absent or invalid")
    url, data = _request_data(provider, model, prompt)
    headers = {"Content-Type": "application/json"}
    if provider == "gemini":
        headers["x-goog-api-key"] = key
    else:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(req, timeout=25) as res:
            raw = res.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Status only: provider response/body and request headers are sensitive.
        raise ValueError(f"Remote AI provider returned HTTP {exc.code}; no retry") from None
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        raise ValueError("Remote AI unavailable or rejected redirect; no retry") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Remote AI response exceeds size cap")
    try:
        result = json.loads(raw)
        if provider == "gemini":
            generated = result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            generated = result["choices"][0]["message"]["content"]
        if not isinstance(generated, str):
            raise TypeError("Nontext model output")
    except (ValueError, KeyError, IndexError, TypeError):
        raise ValueError("Remote AI response malformed; no downstream evidence") from None
    return parse_response(spec, provider, model, generated)
