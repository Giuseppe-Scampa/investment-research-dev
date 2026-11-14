"""Source-gated historical equity ratios: synthetic B screening and made-up figures."""
from __future__ import annotations

import copy
import json

import pytest

from investresearch.cli import ROOT
from investresearch.research_screen import screen
from investresearch.research_valuation import build_valuation,write_valuation,INPUT,_sha

BUNDLE=ROOT/"data/research/demo"


def fixture():
    screening=screen(BUNDLE)
    item=next(r for r in screening["results"] if r.get("market_score") is not None
              and r.get("asset_type")=="EQUITY")
    record={
        "id":item["id"],"currency":item["currency"],
        "fiscal_period_end":"2026-06-30",
        "reference_date":"2026-10-31",
        "values":{
            "market_cap":"1000000000",
            "net_income":"100000000",
            "ebitda":"300000000",
            "free_cash_flow":"80000000",
            "net_debt":"200000000",
        },
        "sources":[
            {"url":"https://www.sec.gov/Archives/edgar/data/1000/issuer-fixture",
             "published_date":"2026-09-30","sha256":None,
             "document_kind":"ISSUER_INTERIM_FILING"},
            {"url":"https://www.nasdaq.com/market-activity/fictional-market-cap",
             "published_date":"2026-10-31","sha256":None,
             "document_kind":"EXCHANGE_MARKET_CAP_REFERENCE"},
        ],
    }
    manual={"schema_version":INPUT,"as_of":screening["as_of"],
            "screening_sha256":_sha(screening),
            "records":[record]}
    return screening,manual,item


def test_ratio_calculator_keeps_unverified_fact_gates_and_no_rank_effect(tmp_path):
    s,manual,entry=fixture()
    original=build_valuation(s)
    assert original["source_asserted_valuations_count"]==0
    assert all(all(v is None for v in item["ratios"].values())
               for item in original["items"])
    report=build_valuation(s,manual)
    r=next(x for x in report["items"] if x["id"]==entry["id"])
    assert report["source_asserted_valuations_count"]==1
    assert r["ratios"]["historical_earnings_yield"]=="0.100000"
    assert r["ratios"]["historical_free_cash_flow_yield"]=="0.080000"
    assert r["ratios"]["historical_ev_to_ebitda"]=="4.000000"
    assert r["ratios"]["historical_market_cap_to_net_income"]=="10.000000"
    assert r["ratios"]["net_debt_to_ebitda"]=="0.666667"
    assert not r["trade_ready"] and not report["rank_or_tax_effect"]
    assert not r["independent_source_claim_verification"]
    write_valuation(report,tmp_path/"out",repo_root=ROOT)
    assert json.loads((tmp_path/"out/RESEARCH_VALUATION.json").read_text())==report


def test_negative_earnings_gives_nonpositive_pe_unknown_not_cheap():
    s,m,entry=fixture()
    m["records"][0]["values"]["net_income"]="-100000000"
    r=next(x for x in build_valuation(s,m)["items"] if x["id"]==entry["id"])
    assert r["ratios"]["historical_market_cap_to_net_income"] is None
    assert r["ratios"]["historical_earnings_yield"]=="-0.100000"


@pytest.mark.parametrize("mutation",[
    "hash","future_market","future_filing","currency","missing_input",
    "zero_cap","nan","missing_cap_source","bad_url","unranked",
    "duplicate","unknown_field","other_provider",
])
def test_valuation_source_integrity_gates_reject_unsupported_numbers(mutation):
    s,m,entry=fixture()
    r=m["records"][0]
    if mutation=="hash":m["screening_sha256"]="f"*64
    elif mutation=="future_market":r["reference_date"]="2027-01-01"
    elif mutation=="future_filing":r["sources"][0]["published_date"]="2027-01-01"
    elif mutation=="currency":r["currency"]="ZZZ"
    elif mutation=="missing_input":del r["values"]["net_income"]
    elif mutation=="zero_cap":r["values"]["market_cap"]="0"
    elif mutation=="nan":r["values"]["free_cash_flow"]="NaN"
    elif mutation=="missing_cap_source":r["sources"][1]["document_kind"]="COMPANY_RELEASE"
    elif mutation=="bad_url":r["sources"][0]["url"]="http://127.0.0.1/secret"
    elif mutation=="unranked":
        r["id"]=next(x["id"] for x in s["results"] if x["market_score"] is None)
    elif mutation=="duplicate":m["records"].append(copy.deepcopy(r))
    elif mutation=="unknown_field":r["values"]["estimated_future_return"]="1"
    elif mutation=="other_provider":r["sources"][1]["document_kind"]="PAID_PROVIDER_FEED"
    with pytest.raises(ValueError):
        build_valuation(s,m)


def test_partial_filing_values_preserve_missingness_and_valid_pe_without_imputation():
    s,m,entry=fixture()
    vals=m["records"][0]["values"]
    vals["ebitda"]=None
    vals["free_cash_flow"]=None
    vals["net_debt"]=None
    report=build_valuation(s,m)
    r=next(x for x in report["items"] if x["id"]==entry["id"])
    assert r["status"]=="PARTIAL_SOURCE_ASSERTED_RATIOS_MISSING_FACTS_NOT_IMPUTED"
    assert r["missing_financial_fields"]==["ebitda","free_cash_flow","net_debt"]
    assert r["source_values"]["ebitda"] is None
    assert r["ratios"]["historical_earnings_yield"]=="0.100000"
    assert r["ratios"]["historical_market_cap_to_net_income"]=="10.000000"
    assert r["ratios"]["historical_free_cash_flow_yield"] is None
    assert r["ratios"]["historical_ev_to_ebitda"] is None
    assert r["ratios"]["net_debt_to_ebitda"] is None
    assert report["source_asserted_valuations_count"]==1
    assert report["source_asserted_ratio_count"]==2
    assert report["rank_or_tax_effect"] is False
    assert report["trade_ready"] is False


def test_missing_entire_filing_financial_profile_is_rejected_even_with_market_cap():
    s,m,_=fixture()
    for name in ("net_income","ebitda","free_cash_flow","net_debt"):
        m["records"][0]["values"][name]=None
    with pytest.raises(ValueError,match="at least one"):
        build_valuation(s,m)
