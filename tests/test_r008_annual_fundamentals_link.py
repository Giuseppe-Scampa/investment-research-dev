"""R-008: source-linked SEC/ESEF evidence is descriptive and fail-closed."""
from __future__ import annotations
import copy
import json
from datetime import date

import pytest
from investresearch.cli import ROOT
from investresearch.research_screen import screen
from investresearch.research_fundamentals_link import (
    build_fundamental_links,write_fundamental_links,VERSION,LINK_SCHEMA,_digest,
    SEC_MODE,EU_MODE)
from investresearch.research_cli import main

BUNDLE=ROOT/"data/research/demo"
ISIN_US="US0378331005"
ISIN_EU="IE00B4L5Y983"


def fixture():
    s=screen(BUNDLE)
    us=next(x for x in s["results"] if x["id"]=="DEMO_TECH")
    eu=next(x for x in s["results"] if x["id"]=="DEMO_GRID")
    us["isin"]=ISIN_US
    eu["isin"]=ISIN_EU
    links={"schema_version":LINK_SCHEMA,"as_of":s["as_of"],
           "screening_sha256":_digest(s),
           "links":[
               {"id":us["id"],"isin":ISIN_US,"provider":"SEC_EDGAR",
                "source_key":"TEST","source_cik":"0000000001",
                "verification":"OPERATOR_ASSERTED_IDENTITY_NOT_CERTIFIED"},
               {"id":eu["id"],"isin":ISIN_EU,"provider":"EU_ESEF",
                "source_key":"ESEF_TEST","source_cik":"",
                "verification":"OPERATOR_ASSERTED_IDENTITY_NOT_CERTIFIED"},
           ]}
    sec={"mode":SEC_MODE,"as_of":s["as_of"],
         "results":[{
             "ticker":"TEST","cik":"0000000001","venue":us["venue"],
             "status":"SEC_ANNUAL_EVIDENCE_AVAILABLE_NO_MARKET_RANK",
             "source_sha256":"b"*64,
             "source_url":"https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json",
             "filing_date":"2026-04-15","period_end":"2025-12-31",
             "revenue_usd":"1000","net_income_usd":"100",
             "net_margin_pct":"10.00",
             "comparison_status":"COMPARABLE_SAME_SEC_FILING",
         }]}
    eu_report={"mode":EU_MODE,"as_of":s["as_of"],
               "results":[{
                   "id":"ESEF_TEST","isin":ISIN_EU,"format":"ESEF_XHTML",
                   "document_sha256":"c"*64,
                   "source_url_declared":"https://reports.example.test/issuer.xhtml",
                   "published_date_declared":"2026-04-30",
                   "fiscal_year_end":"2025-12-31",
                   "ixbrl":{"candidate_count":4},
               }]}
    return s,links,sec,eu_report


def test_source_link_reconciles_two_original_evidence_origins_without_rank_change(tmp_path):
    s,links,sec,eu=fixture()
    old_scores=[x["market_score"] for x in s["results"]]
    report=build_fundamental_links(s,links,sec_report=sec,eu_report=eu)
    assert report["schema_version"]==VERSION
    assert report["source_linked_count"]==2
    assert report["sec_source_linked_count"]==1
    assert report["eu_source_linked_count"]==1
    assert len(report["entries"])==len(s["results"])
    us=next(x for x in report["entries"] if x["id"]=="DEMO_TECH")
    assert us["net_margin_pct"]=="10.00"
    assert us["status"]=="SEC_ANNUAL_FACTS_CROSSWALK_OPERATOR_ASSERTED_NOT_CERTIFIED"
    eurow=next(x for x in report["entries"] if x["id"]=="DEMO_GRID")
    assert eurow["ixbrl_candidate_count"]==4
    assert eurow["status"]=="ESEF_DOCUMENT_AND_IFRS_CANDIDATES_NOT_FACT_VERIFIED"
    assert report["fundamental_facts_certified"] is False
    assert report["rank_or_tax_effect"] is False
    assert report["trade_ready"] is False
    assert [x["market_score"] for x in s["results"]]==old_scores
    write_fundamental_links(report,tmp_path/"out",repo_root=ROOT)
    assert json.loads((tmp_path/"out/RESEARCH_ANNUAL_FACTS.json").read_text())==report


@pytest.mark.parametrize("mutate",[
    "wrong_screen_hash","wrong_isin","duplicate_link","future_sec_filing",
    "false_sec_margin","unmatched_sec_cik","future_eu","wrong_eu_isin",
    "wrong_source_sha","unusable_sec","missing_original_provider",
    "fake_verified_link","mismatched_sec_url","insecure_eu_url",
])
def test_operator_crosswalk_never_certifies_issuer_or_silently_joins(mutate):
    s,links,sec,eu=fixture()
    if mutate=="wrong_screen_hash":
        links["screening_sha256"]="0"*64
    elif mutate=="wrong_isin":
        links["links"][0]["isin"]=ISIN_EU
    elif mutate=="duplicate_link":
        links["links"].append(copy.deepcopy(links["links"][0]))
    elif mutate=="future_sec_filing":
        sec["results"][0]["filing_date"]="2027-01-01"
    elif mutate=="false_sec_margin":
        sec["results"][0]["net_margin_pct"]="11.00"
    elif mutate=="unmatched_sec_cik":
        links["links"][0]["source_cik"]="0000000002"
    elif mutate=="future_eu":
        eu["results"][0]["published_date_declared"]="2027-01-01"
    elif mutate=="wrong_eu_isin":
        eu["results"][0]["isin"]=ISIN_US
    elif mutate=="wrong_source_sha":
        sec["results"][0]["source_sha256"]="not-a-hash"
    elif mutate=="unusable_sec":
        sec["results"][0]["status"]="SEC_ANNUAL_STALE_REVIEW_NO_MARKET_RANK"
    elif mutate=="missing_original_provider":
        sec=None
    elif mutate=="fake_verified_link":
        links["links"][0]["verification"]="INDEPENDENTLY_VERIFIED"
    elif mutate=="mismatched_sec_url":
        sec["results"][0]["source_url"]="https://data.sec.gov/api/xbrl/companyfacts/CIK0000000002.json"
    elif mutate=="insecure_eu_url":
        eu["results"][0]["source_url_declared"]="http://example.test/report"
    with pytest.raises(ValueError):
        build_fundamental_links(s,links,sec_report=sec,eu_report=eu)


def test_no_automatic_ticker_isin_link_without_operator_crosswalk():
    s,links,sec,eu=fixture()
    links["links"]=[]
    output=build_fundamental_links(s,links,sec_report=sec,eu_report=eu)
    assert output["source_linked_count"]==0
    assert all(r["provider"] is None for r in output["entries"])
    assert output["trade_ready"] is False


def test_cli_source_link_offline_never_uses_network(tmp_path):
    s,links,sec,eu=fixture()
    # Unmodified B demo input has no ISIN. Empty source joins remain a valid
    # source-coverage diagnostic; do not use a forged screening file.
    real=screen(BUNDLE)
    links["screening_sha256"]=_digest(real)
    links["links"]=[]
    p=tmp_path/"links.json";p.write_text(json.dumps(links))
    q=tmp_path/"sec.json";q.write_text(json.dumps(sec))
    main(["annual-fundamentals","--bundle",str(BUNDLE),
          "--identity-links",str(p),"--sec-report",str(q),
          "--output",str(tmp_path/"output")])
    result=json.loads((tmp_path/"output/RESEARCH_ANNUAL_FACTS.json").read_text())
    assert result["source_linked_count"]==0
    assert not result["trade_ready"]
