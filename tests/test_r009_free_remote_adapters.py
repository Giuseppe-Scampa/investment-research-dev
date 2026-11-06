"""R-009 remote-free adapters: fully offline synthetic endpoint and security tests."""
from __future__ import annotations

import json
import urllib.error
from urllib.request import ProxyHandler

import pytest

from investresearch import ai_counteranalysis as ai
from investresearch import ai_remote_free as remote
from investresearch.ai_provider_review import reconcile
from investresearch.research_cli import main


SPEC = {
    "schema_version": ai.SCHEMA,
    "data_scope": ai.PUBLIC_ONLY,
    "as_of": "2026-11-05",
    "question": "What uncertainty should be checked in a fictional issuer excerpt?",
    "sources": [{
        "source_id": "SRC1",
        "url": "https://issuer.example.test/filings/fictitious",
        "published_date": "2026-11-04",
        "excerpt": "Fictional issuer reported a synthetic operating-margin improvement.",
        "sha256": None,
    }],
}
ANSWER = {
    "summary": "The excerpt alone cannot establish sustainability.",
    "counterarguments": [{"claim": "Synthetic margins may reverse.", "source_ids": ["SRC1"]}],
    "uncertainties": ["Full original filing is not independently checked."],
}
MODEL = {
    "gemini": "gemini-2.5-flash-lite",
    "groq": "openai/gpt-oss-20b",
    "openrouter": "google/gemma-3-27b-it:free",
}


def _mock_network(monkeypatch, provider, *, generated=None):
    calls = []
    answer = ANSWER if generated is None else generated
    if provider == "gemini":
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
    else:
        body = {"choices": [{"message": {"content": json.dumps(answer)}}]}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            assert size == ai.MAX_RESPONSE_BYTES + 1
            return json.dumps(body).encode()

    class Opener:
        def open(self, req, timeout):
            calls.append(req)
            assert timeout <= 25
            assert req.get_method() == "POST"
            return Reply()

    def build_opener(*handlers):
        proxies = [x for x in handlers if isinstance(x, ProxyHandler)]
        assert len(proxies) == 1 and proxies[0].proxies == {}
        redirects = [x for x in handlers if isinstance(x, remote._NoRedirect)]
        assert len(redirects) == 1
        with pytest.raises(ValueError, match="redirect"):
            redirects[0].redirect_request(None, None, 302, "x", {}, "https://unsafe.test")
        return Opener()

    monkeypatch.setattr(remote.urllib.request, "build_opener", build_opener)
    return calls


@pytest.mark.parametrize("provider", ["gemini", "groq", "openrouter"])
def test_single_opt_in_request_is_bounded_and_does_not_fallback(monkeypatch, provider):
    seen = _mock_network(monkeypatch, provider)
    result = remote.invoke_free_remote(
        SPEC, provider, MODEL[provider], api_key="synthetic-token-not-secret",
        explicitly_authorized=True, free_tier_acknowledged=True,
    )
    assert result == ANSWER
    assert len(seen) == 1
    req = seen[0]
    assert req.full_url.startswith(remote.ENDPOINTS[provider])
    payload = json.loads(req.data)
    if provider == "gemini":
        assert payload["generationConfig"]["maxOutputTokens"] <= 800
        assert req.get_header("X-goog-api-key") == "synthetic-token-not-secret"
    else:
        assert payload["model"] == MODEL[provider]
        assert payload["stream"] is False
        assert payload["max_tokens"] <= 800
        assert req.get_header("Authorization") == "Bearer synthetic-token-not-secret"
        assert "models" not in payload
        assert "tools" not in payload


@pytest.mark.parametrize("provider", ["gemini", "groq", "openrouter"])
def test_manual_authorization_and_secret_are_required_before_network(monkeypatch, provider):
    monkeypatch.setattr(remote.urllib.request, "build_opener",
                        lambda *args: pytest.fail("unexpected external request"))
    for grant, ack in [(False, True), (True, False), (False, False)]:
        with pytest.raises(ValueError, match="opt-in"):
            remote.invoke_free_remote(SPEC, provider, MODEL[provider],
                                      explicitly_authorized=grant,
                                      free_tier_acknowledged=ack, api_key="x")
    with pytest.raises(ValueError, match="secret"):
        remote.invoke_free_remote(SPEC, provider, MODEL[provider],
                                  explicitly_authorized=True,
                                  free_tier_acknowledged=True, api_key="")


@pytest.mark.parametrize("provider,model", [
    ("gemini", "gemini-2.5-pro"),
    ("gemini", "gemini-2.0-flash"),
    ("groq", "llama-3.1-8b-instant"),
    ("groq", "llama-3.3-70b-versatile"),
    ("openrouter", "openai/gpt-4o"),
    ("openrouter", "openrouter/free"),
    ("openrouter", "google/gemma-3-27b-it:floor"),
    ("openrouter", "google/gemma-3-27b-it:free:online"),
    ("openrouter", "google/gemma-3-27b-it:free,openai/paid"),
    ("ollama-local", "test"),
])
def test_paid_unknown_or_fallback_model_refused_before_network(monkeypatch, provider, model):
    monkeypatch.setattr(remote.urllib.request, "build_opener",
                        lambda *args: pytest.fail("paid or unsupported model was invoked"))
    with pytest.raises(ValueError, match="approved|Only Gemini"):
        remote.invoke_free_remote(SPEC, provider, model,
            api_key="fake", explicitly_authorized=True, free_tier_acknowledged=True)


def test_provider_errors_are_sanitized_no_retry_and_no_secret(monkeypatch):
    count = []

    class FailingOpener:
        def open(self, req, timeout):
            count.append(req)
            raise urllib.error.HTTPError(req.full_url, 429, "key-please-never-print",
                                         {}, None)

    monkeypatch.setattr(remote.urllib.request, "build_opener",
                        lambda *args: FailingOpener())
    with pytest.raises(ValueError, match="HTTP 429; no retry") as err:
        remote.invoke_free_remote(SPEC, "groq", MODEL["groq"],
            api_key="synthetic-super-secret", explicitly_authorized=True,
            free_tier_acknowledged=True)
    assert len(count) == 1
    assert "synthetic-super-secret" not in str(err.value)


def test_invalid_source_or_model_citation_never_becomes_financial_fact(monkeypatch):
    bad = dict(ANSWER)
    bad["counterarguments"] = [{"claim": "unsupported", "source_ids": ["MADE_UP"]}]
    seen = _mock_network(monkeypatch, "groq", generated=bad)
    with pytest.raises(ValueError, match="citation IDs"):
        remote.invoke_free_remote(SPEC, "groq", MODEL["groq"],
            api_key="synthetic", explicitly_authorized=True, free_tier_acknowledged=True)
    assert len(seen) == 1


def test_remote_records_reconcile_as_unverified_without_tax_or_rank_effect():
    one = ai.counteranalysis_record(
        SPEC, "groq", MODEL["groq"], ANSWER, remote_call=True)
    two = ai.counteranalysis_record(
        SPEC, "gemini", MODEL["gemini"], ANSWER, remote_call=True)
    assert one["execution"] == "OPT_IN_FREE_TIER_REMOTE"
    assert one["api_billing_status"] == "FREE_TIER_OPERATOR_ACKNOWLEDGED_BILLING_NOT_ATTESTED"
    result = reconcile([one, two])
    assert result["provider_count"] == 2
    assert result["trade_ready"] is False
    assert result["citation_claim_support_fact_checked"] is False
    assert result["rank_or_tax_authorization"] is False


def test_cli_stays_offline_without_both_consents(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(remote.urllib.request, "build_opener",
                        lambda *args: pytest.fail("unexpected remote request"))
    spec = tmp_path / "public.json"
    spec.write_text(json.dumps(SPEC))
    command = ["ai-countercheck", "--spec", str(spec),
               "--provider", "groq", "--model", MODEL["groq"],
               "--invoke-free-remote", "--acknowledge-public-only",
               "--output", str(tmp_path / "out")]
    with pytest.raises(SystemExit) as ex:
        main(command)
    assert ex.value.code == 2
    assert "acknowledge-free-tier" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
