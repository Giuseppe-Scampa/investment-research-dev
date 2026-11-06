"""M5: multiple public-only AI critiques are *not* source fact-checks or ranks."""
from __future__ import annotations

import copy
import json

import pytest

from investresearch.ai_counteranalysis import counteranalysis_record,PUBLIC_ONLY,SCHEMA
from investresearch.ai_provider_review import reconcile,write_reconciliation


def records():
    spec={
        "schema_version":SCHEMA,"data_scope":PUBLIC_ONLY,
        "as_of":"2026-11-05",
        "question":"What could invalidate the revenue-growth thesis for an issuer?",
        "sources":[{"source_id":"SOURCE_A","url":"https://www.sec.gov/Archives/edgar/data/1000/example",
                    "published_date":"2026-11-03",
                    "excerpt":"The hypothetical issuer has uncertain gross margin development.",
                    "sha256":None}],
    }
    a={
        "summary":"Costs and margins could undermine the expected revenue scenario.",
        "counterarguments":[{"claim":"Input cost pressure may impair recovery.",
                             "source_ids":["SOURCE_A"]}],
        "uncertainties":["The given excerpt does not establish full accounting detail."],
    }
    b={
        "summary":"An external analyst independently questions margin assumptions.",
        "counterarguments":[{"claim":"Input cost pressure may impair recovery.",
                             "source_ids":["SOURCE_A"]},
                            {"claim":"Working capital could erode funding flexibility.",
                             "source_ids":["SOURCE_A"]}],
        "uncertainties":["No independent financial valuation attached."],
    }
    return (
        counteranalysis_record(spec,"ollama-local","llama3-test",a,local_call=True),
        counteranalysis_record(spec,"gemini","gemini-test",b,local_call=False),
    )


def test_two_providers_have_literal_overlap_not_independent_factual_agreement(tmp_path):
    a,b=records()
    result=reconcile([a,b])
    assert result["provider_count"]==2
    assert result["unique_literal_claims"]==2
    assert result["literal_overlaps"]==1
    assert result["trade_ready"] is False
    assert result["rank_or_tax_authorization"] is False
    assert result["semantic_agreement_verified"] is False
    assert result["citation_claim_support_fact_checked"] is False
    assert all(not row["independently_fact_checked"] for row in result["human_fact_check_queue"])
    write_reconciliation(result,tmp_path/"private",repo_root=tmp_path/"public")
    assert json.loads((tmp_path/"private/AI_PROVIDER_RECONCILIATION.json").read_text())==result
    with pytest.raises(ValueError,match="overwrite"):
        write_reconciliation(result,tmp_path/"private",repo_root=tmp_path/"public")


@pytest.mark.parametrize("change",[
    "duplicate_provider","different_input","different_date","source_url","future",
    "response_hash","trade","billing","paid_remote","claim_source","missing_sources",
])
def test_invalid_or_unpaired_provider_claims_fail_closed(change):
    a,b=records()
    a,b=copy.deepcopy(a),copy.deepcopy(b)
    if change=="duplicate_provider":b["provider"]="ollama-local"
    elif change=="different_input":b["input_sha256"]="f"*64
    elif change=="different_date":b["research_as_of"]="2026-11-04"
    elif change=="source_url":b["sources"][0]["url"]="https://evil.example/source"
    elif change=="future":b["sources"][0]["published_date"]="2027-01-01"
    elif change=="response_hash":b["response_sha256"]="0"*64
    elif change=="trade":b["rank_or_tax_authorization"]=True
    elif change=="billing":b["api_billing_status"]="UNKNOWN_COST"
    elif change=="paid_remote":b["execution"]="OPT_IN_LOCAL_OLLAMA"
    elif change=="claim_source":b["counterarguments"][0]["source_ids"]=["UNREGISTERED"]
    elif change=="missing_sources":b["sources"]=[]
    with pytest.raises(ValueError):
        reconcile([a,b])


def test_model_output_cannot_replace_primary_source_or_create_trade_recommendation():
    a,b=records()
    r=reconcile([a,b])
    assert r["billing_claim"]=="NO_REMOTE_OR_PAID_PROVIDER_CALLED_BY_RECONCILIATION"
    assert not any("expected_returns" in x for x in r["human_fact_check_queue"])
    assert r["human_fact_check_queue"][0]["required_human_action"]
