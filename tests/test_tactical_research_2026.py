"""Decision 2026 tactical queue. Every external row below is SYNTHETIC TEST DATA."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from investresearch.research_bundle import EXTERNAL, SYNTHETIC
from investresearch.research_funnel import EXTERNAL_STATUS
from investresearch.research_screen import screen
from investresearch.tactical_research import build_tactical, write_tactical
from investresearch.tax_engine import FiscalRegistry
from investresearch.research_cli import main
from investresearch.cli import ROOT

FISCAL = ROOT/"config/fiscal/rules_2026.json"

SAMPLE = [
    ("FSLR","First Solar","US3364331070","EQUITY","Technology","XNAS"),
    ("IFX","Infineon","DE0006231004","EQUITY","Semiconductors","XETR"),
    ("SMH","VanEck Semiconductor ETF","IE00BMC38736","ETF_UCITS","Semiconductors","XMIL"),
    ("WNAS","WisdomTree Nasdaq ETN","XS3003325795","ETN","Nasdaq technology","XMIL"),
    ("COPA","WisdomTree Copper ETC","GB00B15KXQ89","ETC","Industrial metals","XMIL"),
    ("SANOFI","Sanofi","FR0000120578","EQUITY","Pharma","XPAR"),
]


def registry():
    return FiscalRegistry.load(FISCAL)


def good_row(ticker, name, isin, kind, sector, venue, score=65):
    # Hand-made values are ONLY a unit-test fabrication. Production CLI calls
    # screen(bundle), not this function or any imported authored rank CSV.
    return {
        "id":ticker, "name":name, "isin":isin,
        "asset_type":kind, "sector":sector, "venue":venue,
        "currency":"EUR", "status":EXTERNAL_STATUS, "blocking_constraints":[],
        "warnings":[], "market_score":score,
        "price_sha256":"a"*64,
        "price_source_url":"https://www.example.org/test-only-source",
        "last_price_session":"2026-11-04",
        "history_quality":{"verified":True},
        "trade_ready":False,
        "market_metrics":{
            "volatility_20":0.32, "max_drawdown_60":-0.12,
            "momentum_20":0.05, "momentum_60":0.11,
            "avg_daily_turnover_eur_20":1400000.0,
        },
    }


def report(rows=None, mode=EXTERNAL):
    if rows is None:
        rows=[good_row(*p,score=70+i) for i,p in enumerate(SAMPLE)]
    return {"schema_version":1,"as_of":"2026-11-04",
            "dataset_mode":mode, "dataset_manifest_sha256":"b"*64,
            "universe_size":len(rows), "results":rows}


def test_class_spread_no_cross_asset_buy_claim_or_tax_assumption():
    r=build_tactical(report(),fiscal_registry=registry())
    assert r["status"]=="PROVISIONAL_TACTICAL_RESEARCH_PRIORITIES_NOT_TRADE_READY"
    assert not r["trade_ready"] and r["final_investment_shortlist"]==[]
    assert r["r007_global_funnel_status"]=="UNCHANGED_NOT_SUBSTITUTED"
    assert r["instrument_count"]==6 and r["excluded_count"]==0
    assert r["coverage"]["eligible_by_asset_type"]=={
        "EQUITY":3,"ETC":1,"ETF_UCITS":1,"ETN":1}
    assert len(r["research_priorities_by_type"])==6
    by={x["asset_type"]:x for x in r["research_priorities_by_type"]}
    assert by["ETF_UCITS"]["fiscal_gain_research"]["gain_category"]=="REDDITI_CAPITALE"
    assert "ETF_OR_OTHER_CAPITAL_INCOME_GAINS_CANNOT_USE_LOSS_WALLET" in by["ETF_UCITS"]["blocking_evidence_gaps"]
    assert by["ETC"]["fiscal_gain_research"]["gain_category"]=="REVIEW_REQUIRED"
    assert by["ETN"]["fiscal_gain_research"]["gain_category"]=="REVIEW_REQUIRED"
    assert by["EQUITY"]["fiscal_gain_research"]["gain_category"]=="REDDITI_DIVERSI"
    assert not by["EQUITY"]["fiscal_gain_research"]["specific_isin_verification"]
    assert all(not x["trade_ready"] and x["recommendation"]=="NONE" for x in r["research_priorities_by_type"])
    assert "NOT_APPLIED" in r["tax_wallet_status"]


def test_real_candidate_missing_isin_is_excluded_not_ranked():
    rows=[good_row(*SAMPLE[0])]
    rows[0]["isin"]=""
    r=build_tactical(report(rows),fiscal_registry=registry())
    assert r["status"]=="REAL_DATA_INSUFFICIENT_NO_RESEARCH_PRIORITIES"
    assert r["research_priorities_by_type"]==[]
    assert "UNVERIFIED_ISIN" in r["exclusions"][0]["reasons"]


def test_blocked_sector_gold_oil_price_history_and_stale_are_excluded():
    rows=[good_row(*SAMPLE[0]) for _ in range(4)]
    for i,row in enumerate(rows):row["id"]=f"ROW{i}"
    rows[0]["blocking_constraints"]=["oil"]
    rows[1]["history_quality"]["verified"]=False
    rows[2]["status"]="INCOMPLETE_NO_RANK"
    rows[3]["trade_ready"]=True
    r=build_tactical(report(rows),fiscal_registry=registry())
    assert r["excluded_count"]==4
    assert r["research_priorities_by_type"]==[]


def test_synthetic_demo_not_promoted_even_with_high_scores():
    rows=[good_row(*SAMPLE[0],score=100)]
    rows[0]["status"]="DEMO_RANK_NOT_REAL_MARKET"
    rows[0]["isin"]=""
    rows[0]["price_source_url"]=""
    r=build_tactical(report(rows,SYNTHETIC),fiscal_registry=registry())
    assert r["status"]=="SYNTHETIC_DIAGNOSTIC_NO_INVESTMENT_QUEUE"
    assert r["research_priorities_by_type"]==[]
    assert r["final_investment_shortlist"]==[]


def test_r007_threshold_not_modified_or_bypassed():
    from investresearch.research_funnel import DEFAULT_POLICY,build_funnel
    small=report()
    tactical=build_tactical(small,fiscal_registry=registry())
    full=build_funnel(small)
    assert len(tactical["research_priorities_by_type"])==6
    assert full["status"]=="INSUFFICIENT_RESEARCH_UNIVERSE_NO_SHORTLIST"
    assert not full["stage_1_pool"]
    assert DEFAULT_POLICY["min_universe"]==200
    assert DEFAULT_POLICY["min_ranked"]==100


def test_12_limit_4_per_type_no_cross_asset_score_ranking():
    rows=[]
    samples=[SAMPLE[0],SAMPLE[2],SAMPLE[3],SAMPLE[4]]
    for group,(t,n,isn,typ,sec,venue) in enumerate(samples):
        for i in range(7):
            r=good_row(f"{t}_{i}",n,isn,typ,sec,venue,score=20+i+group*7)
            rows.append(r)
    tactical=build_tactical(report(rows),fiscal_registry=registry())
    priorities=tactical["research_priorities_by_type"]
    assert len(priorities)==12
    from collections import Counter
    count=Counter(r["asset_type"] for r in priorities)
    assert max(count.values())==3
    # First round ordered alphabetically by class, not global score.
    assert [p["asset_type"] for p in priorities[:4]]==["EQUITY","ETC","ETF_UCITS","ETN"]
    assert priorities[0]["historical_market_score"]==26


@pytest.mark.parametrize("field,value",[
    ("schema_version",99),("dataset_mode","UNKNOWN"),
    ("dataset_manifest_sha256","bad"),
    ("universe_size",99),("as_of","2027-01-01"),
])
def test_manifest_invariants(field,value):
    src=report()
    src[field]=value
    with pytest.raises(ValueError):
        build_tactical(src,fiscal_registry=registry())


def test_duplicate_missing_id_and_bad_fiscal_registry_rejected():
    src=report([good_row(*SAMPLE[0]),good_row(*SAMPLE[0])])
    with pytest.raises(ValueError,match="Duplicate"):
        build_tactical(src,fiscal_registry=registry())
    src=report()
    with pytest.raises(ValueError,match="FiscalRegistry"):
        build_tactical(src,fiscal_registry=None)


def test_extra_unknown_asset_type_does_not_claim_tax_eligibility():
    row=good_row(*SAMPLE[0])
    row["asset_type"]="UNRECOGNIZED_ETP"
    r=build_tactical(report([row]),fiscal_registry=registry())
    tx=r["research_priorities_by_type"][0]["fiscal_gain_research"]
    assert tx["gain_category"]=="REVIEW_REQUIRED"
    assert tx["tax_research_status"]=="MISSING_OR_AMBIGUOUS_FISCAL_RULE"


def test_private_output_gate_and_formula_escape(tmp_path):
    row=good_row(*SAMPLE[0])
    row["name"]='=HYPERLINK("https://evil.invalid","Click")'
    r=build_tactical(report([row]),fiscal_registry=registry())
    root=tmp_path/"repo"
    with pytest.raises(ValueError,match="private"):
        write_tactical(r,root/"reports"/"generated",repo_root=root)
    output=root/"data"/"private"/"decision2026"
    write_tactical(r,output,repo_root=root)
    data=(output/"TACTICAL_RESEARCH.json").read_text()
    assert "NOT_APPLIED_REQUIRES_PRIVATE_BLOCK_A" in data
    csvtext=(output/"TACTICAL_RESEARCH.csv").read_text()
    assert "'=HYPERLINK" in csvtext
    markdown=(output/"TACTICAL_RESEARCH.md").read_text()
    assert "NO TRADE READY" in markdown
    assert "final investment shortlist" not in markdown.lower()
    assert "&quot;" in markdown


def test_cli_uses_real_screen_from_bundle_not_a_user_authored_rank(tmp_path,capsys):
    # Public demo is intentionally synthetic. CI must show zero trade-ready.
    output=tmp_path/"diagnostic"
    main(["tactical","--bundle",str(ROOT/"data"/"research"/"demo"),
          "--output",str(output)])
    r=json.loads((output/"TACTICAL_RESEARCH.json").read_text())
    assert r["status"]=="SYNTHETIC_DIAGNOSTIC_NO_INVESTMENT_QUEUE"
    assert not r["research_priorities_by_type"]
    assert r["instrument_count"]==7
    assert "0 final investments or orders" in capsys.readouterr().out
