"""R-009: no-cost-by-default, public-only offline counteranalysis tests.

No test contacts a model server or paid API. Financial facts and evidence are
synthetic. Citation ID validation does not constitute content verification.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import ProxyHandler

import pytest

from investresearch import ai_counteranalysis as ai
from investresearch.research_cli import main


def public_spec():
    return {
        "schema_version": ai.SCHEMA,
        "data_scope": ai.PUBLIC_ONLY,
        "as_of": "2026-11-04",
        "question": "What is the most important uncertainty in this illustrative issuer claim?",
        "sources": [{
            "source_id": "SRC1",
            "url": "https://issuer.example.test/investor-relations/statement",
            "published_date": "2026-11-03",
            "excerpt": "Example issuer states that synthetic sales grew during the period.",
            "sha256": None,
        }],
    }


def response():
    return {
        "summary": "The source does not establish future earnings.",
        "counterarguments": [{
            "claim": "Historical sales do not guarantee growth.",
            "source_ids": ["SRC1"],
        }],
        "uncertainties": ["No verified full issuer document is included."],
    }


def test_public_spec_rejects_broker_fields_and_unknown_keys():
    s = public_spec()
    s["tax_wallets"] = [{"vintage": 2022, "remaining_eur": 5000}]
    with pytest.raises(ValueError, match="private data prohibited"):
        ai.validate_public_spec(s)
    s = public_spec()
    s["data_scope"] = "BROKER_PORTFOLIO"
    with pytest.raises(ValueError, match="public research"):
        ai.validate_public_spec(s)


@pytest.mark.parametrize("change,phrase", [
    ({"published_date": "2026-11-05"}, "not yet published"),
    ({"source_id": "invalid lowercase"}, "source ID"),
    ({"url": "http://issuer.example.test/report"}, "HTTPS"),
    ({"url": "https://user:pass@issuer.example.test/"}, "HTTPS"),
    ({"sha256": "NOT_A_SHA"}, "SHA256"),
    ({"excerpt": "Contact my adviser@example.org about the account"}, "potential personal"),
    ({"excerpt": "IBAN IT60X0542811101000000123456"}, "potential personal"),
])
def test_public_source_gate_fail_closed(change, phrase):
    s = public_spec()
    s["sources"][0].update(change)
    with pytest.raises(ValueError, match=phrase):
        ai.validate_public_spec(s)


def test_source_ids_are_unique_and_response_citations_cannot_be_hallucinated():
    s = public_spec()
    s["sources"].append(dict(s["sources"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        ai.validate_public_spec(s)
    s = public_spec()
    answer = response()
    answer["counterarguments"][0]["source_ids"] = ["NONEXISTENT"]
    with pytest.raises(ValueError, match="citation IDs"):
        ai.parse_response(s, "gemini", "model-example", answer)
    answer["counterarguments"][0]["source_ids"] = [["SRC1"]]
    with pytest.raises(ValueError, match="citation IDs"):
        ai.parse_response(s, "groq", "model-example", answer)


def test_response_schema_rejects_trading_actions_and_unstructured_text():
    s = public_spec()
    with pytest.raises(ValueError, match="must be JSON"):
        ai.parse_response(s, "gemini", "model-example", "Buy at 50 now")
    answer = response()
    answer["orders"] = ["BUY"]
    with pytest.raises(ValueError, match="schema invalid"):
        ai.parse_response(s, "openrouter", "model-example", answer)
    with pytest.raises(ValueError, match="model identifier"):
        ai.parse_response(s, "gemini", "../unsafe model", response())


def test_deterministic_public_record_never_marks_fact_checked_or_trade_ready():
    s = public_spec()
    result1 = ai.counteranalysis_record(s, "gemini", "model-example", response())
    result2 = ai.counteranalysis_record(s, "gemini", "model-example", response())
    assert result1 == result2
    assert result1["result_status"] == "AI_UNVERIFIED_COUNTERANALYSIS_HUMAN_REVIEW_REQUIRED"
    assert result1["citation_status"] == "KNOWN_SOURCE_IDS_ONLY_NOT_FACT_CHECKED"
    assert result1["rank_or_tax_authorization"] is False
    assert result1["execution"] == "IMPORTED_RESPONSE_NO_NETWORK"
    assert len(result1["input_sha256"]) == 64
    assert "account_id" not in json.dumps(result1)


def test_local_ollama_refuses_execution_without_explicit_authorization(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network allowed without opt-in")
    monkeypatch.setattr(ai.urllib.request, "build_opener", forbidden)
    with pytest.raises(ValueError, match="authorization"):
        ai.invoke_local_ollama(public_spec(), "llama3:local")


def test_local_ollama_uses_only_proxyless_loopback_and_validates_response(monkeypatch):
    seen = {}

    class FakeReply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return json.dumps({"response": json.dumps(response())}).encode("utf-8")

    class FakeOpener:
        def open(self, request, timeout):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["payload"] = json.loads(request.data)
            seen["timeout"] = timeout
            return FakeReply()

    def build_opener(*handlers):
        proxy = next(x for x in handlers if isinstance(x, ProxyHandler))
        assert proxy.proxies == {}
        redirect = next(x for x in handlers if hasattr(x, "redirect_request"))
        with pytest.raises(ValueError, match="redirects are forbidden"):
            redirect.redirect_request(None,None,302,"redirect",{},"https://external.test")
        return FakeOpener()

    monkeypatch.setattr(ai.urllib.request, "build_opener", build_opener)
    got = ai.invoke_local_ollama(public_spec(), "llama3:local",
                                 explicitly_authorized=True)
    assert got == response()
    assert seen["url"] == "http://127.0.0.1:11434/api/generate"
    assert seen["method"] == "POST"
    assert seen["payload"]["stream"] is False
    assert seen["payload"]["keep_alive"] == 0
    assert "public issuer excerpts" in seen["payload"]["prompt"].lower()


def test_ai_report_private_path_only_and_no_overwrite(tmp_path):
    s = public_spec()
    record = ai.counteranalysis_record(s, "openrouter", "free-model-example", response())
    dest = tmp_path / "private" / "ai"
    ai.write_counteranalysis(record, dest, repo_root=tmp_path / "repo")
    data = json.loads((dest / "AI_COUNTERANALYSIS.json").read_text())
    assert data["rank_or_tax_authorization"] is False
    assert "not fact-checked" in (dest / "AI_COUNTERANALYSIS.md").read_text().lower()
    with pytest.raises(ValueError, match="overwrite"):
        ai.write_counteranalysis(record, dest, repo_root=tmp_path / "repo")
    with pytest.raises(ValueError, match="ignored data/private"):
        ai.write_counteranalysis(record, tmp_path / "repo" / "reports" / "generated",
                                 repo_root=tmp_path / "repo")


def test_cli_requires_explicit_choice_and_public_ack(tmp_path, capsys):
    sp = tmp_path / "spec.json"
    rp = tmp_path / "response.json"
    sp.write_text(json.dumps(public_spec()))
    rp.write_text(json.dumps(response()))
    base = [
        "ai-countercheck", "--spec", str(sp),
        "--provider", "gemini", "--model", "model-example",
        "--response-json", str(rp), "--output", str(tmp_path / "out"),
    ]
    with pytest.raises(SystemExit) as error:
        main(base)
    assert error.value.code == 2
    assert "acknowledge-public-only" in capsys.readouterr().err

    main(base + ["--acknowledge-public-only"])
    assert (tmp_path / "out" / "AI_COUNTERANALYSIS.json").exists()
    assert "no trade authorization" in capsys.readouterr().out

    with pytest.raises(SystemExit):
        main([
            "ai-countercheck", "--spec", str(sp),
            "--provider", "groq", "--model", "model-example",
            "--invoke-local-ollama", "--output", str(tmp_path / "other"),
            "--acknowledge-public-only",
        ])


def test_model_provider_adapter_is_offline_until_validated():
    for provider in ("gemini", "groq", "openrouter", "ollama-local"):
        result = ai.counteranalysis_record(public_spec(), provider,
                                           "unverified-explicit-model", response())
        assert result["execution"] == "IMPORTED_RESPONSE_NO_NETWORK"
    assert "openai" not in ai.PROVIDERS
