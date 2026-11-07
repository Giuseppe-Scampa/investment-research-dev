"""Frozen historic-study protocol: no-lookahead, rejection, alternatives and fees.

ALL prices fabricated. The resulting historical test report is NOT evidence
that the investment ranking predicts returns, nor legal source authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from investresearch.market_calendar import session
from investresearch.research_bundle import build_bundle,SYNTHETIC
from investresearch.research_historical_validation import (
    PROTOCOL,VERSION,protocol_file,validate_historical,
    _candidate,_net_trade,_spearman,_adjusted_eur_prices,write_backtest,
)
from investresearch.cli import ROOT
from investresearch.research_cli import main


def fake_bundle(tmp_path,*,regime='mixed_trends'):
    start=date(2026,1,2)
    end=date(2026,11,6)
    market_days=[]
    day=start
    while day<=end:
        if session(day,"XMIL"):
            market_days.append(day)
        day+=timedelta(days=1)
    assert len(market_days)>190
    assets=[]
    for i in range(6):
        records=["date,close,volume"]
        pivot=sum(d<=date(2026,4,1) for d in market_days)-1
        for j,d in enumerate(market_days):
            # Two predefined fictional regimes: a ranking "success" is
            # never forced. Reversal demonstrates genuine underperformance.
            if regime=='adversarial_reversal':
                if i in (4,5):
                    gross=1+0.002*j if j<=pivot else 1+0.002*pivot-0.003*(j-pivot)
                else:
                    gross=1+0.0001*j if j<=pivot else 1+0.0001*pivot+0.001*(j-pivot)
                price=(92+i*5)*gross
            else:
                growth=(i-2)*.00065
                price=(92+i*5)*(1+growth*j)+.8*math.sin(j/14+i/3)
            records.append(f"{d.isoformat()},{price:.7f},{200000+i*10000}")
        original=tmp_path/f"FICTIONAL_PRICE_SERIES_{i}.csv"
        original.write_text("\n".join(records)+"\n")
        assets.append({
            "id":f"TEST_ONLY_MILAN_{i}",
            "name":f"NOT_MARKET_DATA_EU_{i}",
            "isin":"",
            "asset_type":"EQUITY","venue":"XMIL","currency":"EUR",
            "sector":"FICTIONAL_ELECTRONICS","oil_exposure":"none",
            "prices_source":{
                "provider":"SYNTHETIC_PRICES","path":str(original),
                "source_url":"https://example.test/fictional",
                "sha256":hashlib.sha256(original.read_bytes()).hexdigest(),
            },
        })
    bundle=tmp_path/"FICTIONAL_BUNDLE"
    build_bundle({"mode":SYNTHETIC,"as_of":"2026-11-06",
                  "assets":assets},bundle)
    return bundle


def test_protocol_is_frozen_before_outcomes_and_never_changes_2026_scope():
    policy,sha=protocol_file()
    assert len(sha)==64
    assert policy["portfolio"]["selected_instruments"]==2
    assert policy["portfolio"]["random_portfolios"]==10000
    assert policy["statistics"]["bootstrap_resamples"]==10000
    assert policy["schedule"]["holding_return_intervals"]==30
    assert policy["statistics"]["confidence_level"]==.95
    assert policy["costs"]["minimum_commission_eur_each_side"]==7
    with pytest.raises(ValueError,match="only the previously committed"):
        protocol_file(Path("/tmp/alternative_unregistered_protocol.json"))


def test_retrospective_backtest_can_return_negative_alpha_and_never_certifies_prediction(tmp_path):
    bundle=fake_bundle(tmp_path)
    result=validate_historical(bundle)
    assert result["schema_version"]==VERSION
    assert result["status"]=="SYNTHETIC_NOT_MARKET_EVIDENCE"
    assert result["protocol_sha256"]
    assert result["cohort_at_time_t_only"] is True
    assert result["tax_net_returns_verified"] is False
    assert result["source_rights_and_historical_issuer_universe_verified"] is False
    assert result["trade_ready"] is False
    assert result["predictive_edge_certified"] is False
    assert result["random_portfolio_trials"]==10000
    assert len(result["folds"])>=2
    assert all(len(x["selected_ids"])==2 and x["eligible_instruments"]==6
               and x["rank_information_coefficient"] is not None
               for x in result["folds"])
    assert all(x["entry_next_session"] for x in result["folds"])
    assert result["IC_95pct_bootstrap_CI"] is not None
    assert result["excess_95pct_bootstrap_CI"] is not None
    # Compare the same B model with 10,000 K-count random alternatives:
    assert 0<=result["random_portfolio_percentile"]<=1
    assert -1<=result["mean_IC_spearman"]<=1


def test_adversarial_synthetic_momentum_trap_produces_negative_excess(tmp_path):
    bundle=fake_bundle(tmp_path,regime='adversarial_reversal')
    result=validate_historical(bundle)
    assert result["status"]=="SYNTHETIC_NOT_MARKET_EVIDENCE"
    # Existence of a deliberately losing regime is a mandatory falsification
    # check; the test must not insist that picks always have positive returns.
    assert any(f["excess_vs_universe"]<0 for f in result["folds"])
    assert any(f["selected_net_return"]<0 for f in result["folds"])
    assert result["predictive_edge_certified"] is False


def test_lookahead_canary_and_missing_future_outcome_never_drop_losers(tmp_path):
    bundle=fake_bundle(tmp_path)
    # Invalidate a single original future bar and rehash it as a *synthetic*
    # bundle file. The study must reject an incomplete fold, never silently
    # remove the poorly performing instrument from its benchmark.
    from investresearch.research_bundle import load_bundle
    manifest,items,fx,events=load_bundle(bundle)
    original=list(items[0][1])
    assert original
    # A missing outcome impacts at least one preselected fold. The baseline
    # selection cannot be reoptimized on a later-complete survivor cohort.
    cutoff_index=next(i for i,row in enumerate(original) if row["date"]=="2026-04-01")
    short=original[:cutoff_index+12]
    source=bundle/"prices"/(items[0][0]["id"]+".csv")
    lines=["date,close,volume"]+[f"{r['date']},{r['close']},{r['volume']}" for r in short]
    source.write_text("\n".join(lines)+"\n")
    amended=json.loads((bundle/"manifest.json").read_text())
    for entry in amended["assets"]:
        if entry["id"]==items[0][0]["id"]:
            entry["prices"]["sha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
            entry["prices"]["bytes"]=source.stat().st_size
    (bundle/"manifest.json").write_text(json.dumps(amended))
    try:
        report=validate_historical(bundle)
    except ValueError:
        # Either gate (bundle integrity or truncated history) is fail-closed.
        return
    assert any(f["reason"]=="MISSING_OR_NONCONSECUTIVE_POST_SELECTION_OUTCOME"
               for f in report["folds_rejected"])


def test_same_asof_selection_is_invariant_to_appended_future_data():
    asset={
        "id":"TEST_ONLY_X","name":"NOT_MARKET_DATA_EU",
        "isin":"","asset_type":"EQUITY","venue":"XMIL",
        "sector":"TECH","oil_exposure":"none","currency":"EUR",
    }
    bars=[]
    d=date(2026,3,1)
    while d<=date(2026,8,28):
        if session(d,"XMIL"):
            bars.append((d.isoformat(),Decimal("110")+Decimal(len(bars))*Decimal("0.10"),
                         Decimal("10000")))
        d+=timedelta(days=1)
    t="2026-07-01"
    setting={"exclude_primary_oil":True,"exclude_additional_gold":True,
             "avoid_duplicate_eurostoxx50":False}
    baseline=_candidate(asset,[row for row in bars if row[0]<=t],t,setting)
    assert baseline is not None
    appended=bars+[
        ("2026-09-01",Decimal("1000000"),Decimal("99999"))
    ]
    assert _candidate(asset,appended,t,setting)==baseline
    # A future-return canary must not be accepted as a price column.
    with pytest.raises(ValueError,match="future/target column"):
        _adjusted_eur_prices(asset,[
            {"date":"2026-05-01","close":"100","volume":"1",
             "forward_30d_return":"9999"}],None)


def test_costs_and_commission_floor_cannot_make_positive_pnl_larger():
    dates=[("2026-07-01",Decimal("100"),Decimal("1000")),
           ("2026-07-02",Decimal("110"),Decimal("1000"))]
    net,curve,gross=_net_trade(
        dates,notional=5000,fee_bps=.0019,min_fee=7,fx_bps=.0025,usd=True)
    assert gross==pytest.approx(.1)
    assert net<gross
    assert curve[0]<1
    without_fx,_,_=_net_trade(
        dates,notional=5000,fee_bps=.0019,min_fee=7,fx_bps=.0025,usd=False)
    assert net<without_fx
    floor,_,_=_net_trade(
        dates,notional=200,fee_bps=.0019,min_fee=7,fx_bps=.0025,usd=False)
    zero,_,_=_net_trade(
        dates,notional=200,fee_bps=0,min_fee=0,fx_bps=0,usd=False)
    assert floor<zero


def test_rank_ic_rejects_constant_or_too_small_signal():
    assert _spearman([1,2],[1,2]) is None
    assert _spearman([3,3,3,3],[1,2,3,4]) is None
    assert _spearman([1,2,3,4],[4,3,2,1])==pytest.approx(-1.)
    assert _spearman([1,2,3,4],[1,2,3,4])==pytest.approx(1.)


def test_public_b_historical_results_must_stay_in_private_directory(tmp_path):
    bundle=fake_bundle(tmp_path)
    result=validate_historical(bundle)
    with pytest.raises(ValueError,match="private"):
        write_backtest(result,tmp_path/"public_report.json",repo_root=ROOT)
    # CLI is separately guarded against unreviewed research report paths.
    assert result["folds"] and not result["predictive_edge_certified"]


def test_even_real_b_source_with_tiingo_starter_cannot_be_backtested(tmp_path):
    bundle=fake_bundle(tmp_path)
    m=bundle/"manifest.json"
    original=json.loads(m.read_text())
    original["mode"]="EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE"
    original["assets"][0]["prices"]["provider"]="TIINGO_EOD_PERSONAL_RESEARCH"
    m.write_text(json.dumps(original))
    with pytest.raises(ValueError,match="TIINGO_STARTER_NO_BACKTEST"):
        validate_historical(bundle)


@pytest.mark.parametrize("factor",[
    Decimal("0.6666666667"),  # 3:2 stock split (unadjusted)
    Decimal("0.75"),          # 4:3 stock split
    Decimal("0.80"),          # 5:4 stock split
])
def test_future_unadjusted_split_cannot_masquerade_as_selected_performance(factor):
    from investresearch.research_historical_validation import _outcome
    policy,_=protocol_file()
    cut=date(2026,6,1)
    trading=[]
    d=cut+timedelta(days=1)
    while len(trading)<35:
        if session(d,"XMIL"):
            trading.append(d)
        d+=timedelta(days=1)
    rows=[]
    for n,day in enumerate(trading):
        close=Decimal("100")*(factor if n>=10 else Decimal("1"))
        rows.append((day.isoformat(),close,Decimal("10000")))
    sample={"id":"TEST_ONLY_SPLIT","venue":"XMIL","currency":"EUR","score":40}
    got=_outcome(sample,rows,cut.isoformat(),30,policy["costs"],3)
    assert got is None  # no 30-session alpha claim from a fake split jump


def test_unknown_oil_exposure_is_not_converted_to_approved_historical_universe():
    asset={"id":"TEST_UNKNOWN_OIL","name":"NOT_MARKET_DATA",
           "isin":"","asset_type":"EQUITY","venue":"XMIL","currency":"EUR",
           "oil_exposure":"unknown","sector":"energy"}
    rows=[]
    d=date(2026,5,4)
    while len(rows)<65:
        if session(d,"XMIL"):
            rows.append((d.isoformat(),Decimal("100")+Decimal(len(rows))/100,
                         Decimal("100000")))
        d+=timedelta(days=1)
    cutoff=rows[-1][0]
    assert _candidate(asset,rows,cutoff,{
        "exclude_primary_oil":True,"exclude_additional_gold":True,
        "avoid_duplicate_eurostoxx50":True,
    }) is None
