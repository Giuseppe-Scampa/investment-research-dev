"""R-008 research coverage requires original screen/provenance and rejects gaps.

All input is from the repository's committed SYNTHETIC demo, never quote data.
"""
from __future__ import annotations

import copy
import json
import pytest
from investresearch.cli import ROOT
from investresearch.research_screen import screen
from investresearch.research_evidence import (
    build_evidence, write_evidence, INPUT, _canonical,
)

BUNDLE=ROOT/"data/research/demo"


def sample():
    s=screen(BUNDLE)
    match=next(x for x in s["results"] if x["market_score"] is not None)
    return s,match


def manual(s,match):
    return {
        "schema_version":INPUT, "as_of":s["as_of"],
        "screening_sha256":_canonical(s),
        "research":[{
            "id":match["id"],
            "notes":{
                "valuation":"Issuer annual cash flow and enterprise value require independent review.",
                "macro":"Rates and reference inflation could affect this sector, but no causality is established.",
                "counter_thesis":"The hypothetical margin recovery may fail during a competitive downturn.",
                "geopolitical":"Supply chain dependencies have not been independently reconciled.",
                "factors":"Historical price volatility is only a proxy for systematic exposure.",
            },
            "sources":[{
                "source_id":"ISSUER_1",
                "url":"https://www.sec.gov/Archives/edgar/data/1000/fixture",
                "published_date":"2026-10-15","sha256":None,
                "supports":["valuation","macro","counter_thesis","geopolitical","factors"],
            }],
        }]
    }


def test_demo_matrix_is_explicit_about_unverified_valuation_and_no_model_return(tmp_path):
    s,match=sample()
    evidence=build_evidence(s)
    assert evidence["universe_count"]==s["universe_size"]
    assert evidence["market_ranked_count"]==s["ranked_count"]
    assert evidence["public_research_assertions_count"]==0
    assert evidence["screening_sha256"]==_canonical(s)
    assert evidence["research_ready_for_trade"] is False
    assert evidence["all_gaps"]["VALUATION_NOT_SOURCE_RECONCILED"]==s["universe_size"]
    assert all(item["trade_ready"] is False for item in evidence["items"])
    assert all(item["stress_scenarios_conditional_pct"]==[-30,-15,0,15]
               for item in evidence["items"])
    write_evidence(evidence,tmp_path/"test",repo_root=ROOT)
    assert json.loads((tmp_path/"test/RESEARCH_EVIDENCE.json").read_text())==evidence


def test_source_linked_research_never_promotes_score_or_certifies_claim():
    s,match=sample()
    before=build_evidence(s)
    annotated=build_evidence(s,manual(s,match))
    assert annotated["public_research_assertions_count"]==1
    assert annotated["items"][0]["market_score"]==before["items"][0]["market_score"]
    assert annotated["items"][0]["trade_ready"] is False
    assert annotated["all_gaps"]["MANUAL_SOURCE_CITATIONS_NOT_INDEPENDENTLY_FACT_CHECKED"]==1
    assert annotated["items"][0]["public_references"]


@pytest.mark.parametrize("mut",[
    "hash","asof","bad_id","future","wrong_source","no_support","unknown_field",
    "duplicate_id","bad_url","no_schema","unauthenticated_status",
])
def test_research_assertions_fail_closed(mut):
    s,match=sample()
    p=manual(s,match)
    e=p["research"][0]
    if mut=="hash":p["screening_sha256"]="0"*64
    elif mut=="asof":p["as_of"]="2026-10-30"
    elif mut=="bad_id":e["id"]="DOES_NOT_EXIST"
    elif mut=="future":e["sources"][0]["published_date"]="2027-01-01"
    elif mut=="wrong_source":e["sources"][0]["supports"]=["valuation"]
    elif mut=="no_support":e["sources"]=[]
    elif mut=="unknown_field":e["notes"]["personal_wallet"]="Sensitive 5000 EUR internal bank data"
    elif mut=="duplicate_id":p["research"].append(copy.deepcopy(e))
    elif mut=="bad_url":e["sources"][0]["url"]="http://localhost/private"
    elif mut=="no_schema":del p["schema_version"]
    elif mut=="unauthenticated_status":
        s["results"][0]["status"]="INCOMPLETE_NO_RANK"
        p["screening_sha256"]=_canonical(s)
    with pytest.raises(ValueError):
        build_evidence(s,p)


def test_tampering_screening_aggregate_or_duplicate_identity_is_rejected():
    s,_=sample()
    s["ranked_count"]=500
    with pytest.raises(ValueError,match="count"):
        build_evidence(s)
    s,_=sample()
    s["results"][1]["id"]=s["results"][0]["id"]
    with pytest.raises(ValueError,match="Duplicate"):
        build_evidence(s)
