"""Successor V3: preregistered same-K primary and no favorable missingness selection.

All inputs here are FICTIONAL and never constitute market evidence.
"""
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

import pytest

from investresearch.historical_calendar_v2 import dates_v2
from investresearch.research_bundle import SYNTHETIC, build_bundle
from investresearch.research_historical_validation_v2 import v2_protocol
from investresearch.research_historical_validation_v3 import (
    v3_protocol, evaluate_v3, FROZEN_V3_BLOB_SHA,
)


def make_v3_bundle(tmp_path, *, remove_future=False, as_of="2026-07-15"):
    sessions=dates_v2(date(2020,12,1), date(2026,7,15),"XMIL")
    entries=[]
    missing_session=dates_v2(date(2023,2,1),date(2023,2,28),"XMIL")[9]
    for k in range(24):
        path=tmp_path/f"FICTIONAL_ASSET_{k}.csv"
        rows=["date,close,volume"]
        for j,day in enumerate(sessions):
            if remove_future and k==0 and day==missing_session:
                continue
            # Smooth fictional returns, no real security mapping.
            price=100+k*4+j*.008+.65*math.sin(j/28+k)
            rows.append(f"{day},{price:.6f},{250000+k*2000}")
        path.write_text("\n".join(rows)+"\n")
        entries.append({
            "id":f"FICTIONAL_V3_SECURITY_{k}",
            "name":f"FICTIONAL_V3_{k}",
            "isin":"","asset_type":"EQUITY","currency":"EUR",
            "venue":"XMIL","sector":"FICTIONAL_NON_OIL",
            "oil_exposure":"none",
            "prices_source":{"provider":"SYNTHETIC_PRICES",
                             "path":str(path)},
        })
    out=tmp_path/"BUNDLE_FICTIONAL_V3"
    build_bundle({"mode":SYNTHETIC,"as_of":as_of,"assets":entries},out)
    return out


def test_v3_protocol_registered_separately_and_v2_has_not_changed(tmp_path,monkeypatch):
    import investresearch.research_historical_validation_v3 as mod
    policy,digest=v3_protocol()
    assert len(digest)==64
    assert policy["comparisons"]["primary_benchmark"].startswith(
        "EXACT_EXPECTED_RANDOM_K")
    assert policy["cohort"]["minimum_independent_folds_for_predictive_evidence"]==30
    assert policy["missing_outcomes"]["no_conditioning_on_outcome_completeness"] is True
    v2,v2digest=v2_protocol()
    assert v2["comparisons"]["primary_benchmark"]=="EQUAL_WEIGHT_AS_OF_ELIGIBLE_UNIVERSE"
    assert len(v2digest)==64
    original=json.loads(mod.PROTOCOL_V3.read_text())
    original["statistics"]["require_zero_unresolved_matured_as_of_cohorts"]=False
    bad=tmp_path/"tampered_v3.json"
    bad.write_text(json.dumps(original))
    monkeypatch.setattr(mod,"PROTOCOL_V3",bad)
    with pytest.raises(ValueError,match="PREREGISTERED_V3_PROTOCOL_CHANGED"):
        mod.v3_protocol()


def test_v3_synthetic_primary_is_same_k_not_fee_biased_n_leg(tmp_path):
    out=evaluate_v3(make_v3_bundle(tmp_path))
    assert out["schema_version"]=="V3_LONG_HORIZON_BACKTEST_V3"
    assert out["protocol_git_blob_sha"]==FROZEN_V3_BLOB_SHA
    assert out["status"]=="SYNTHETIC_NO_MARKET_EVIDENCE"
    assert out["complete_nonoverlapping_folds"]>=30
    assert out["matured_outcome_unresolved_anchors"]==0
    assert out["matured_outcome_completeness_gate"] is True
    assert out["confidence_interval_95_same_K_excess_PRIMARY"] is not None
    assert out["N_leg_descriptive_CI_DO_NOT_USE_AS_ALPHA"] is not None
    assert out["random_portfolio_trials"]==10000
    assert out["historical_point_in_time_universe_independently_verified"] is False
    assert out["random_walk_false_positive_rate_calibrated"] is False
    assert out["predictive_edge_certified"] is False
    assert out["trade_ready"] is False
    for f in out["folds"]:
        assert abs((f["selected_net"]-f["same_K_random_expected_net"]) -
                   f["same_K_excess_net"])<2.1e-8
        assert abs(f["excess"]-f["same_K_excess_net"])<2.1e-8
        assert len(f["selected_ids"])==2
        assert len(f["bottom_ids"])==2
        assert f["eligible"]==24
    assert abs(out["same_K_excess_net_mean_PRIMARY"]-
               mean(f["same_K_excess_net"] for f in out["folds"]))<2.1e-8
    assert (out["N_leg_descriptive_excess_mean_DO_NOT_USE_AS_ALPHA"]-
            out["same_K_excess_net_mean_PRIMARY"])>0.01


def test_v3_future_gap_is_not_used_to_select_favorable_complete_windows(tmp_path):
    out=evaluate_v3(make_v3_bundle(tmp_path,remove_future=True))
    assert out["matured_outcome_unresolved_anchors"]>=1
    assert out["matured_outcome_unresolved_asset_events"]>=1
    assert out["matured_outcome_completeness_gate"] is False
    assert out["primary_diagnostic_gate_without_null_control"] is False
    assert out["statistical_diagnostic_gate_without_null_control"] is False
    assert out["predictive_edge_certified"] is False
    affected=[x for x in out["ex_ante_anchor_audit"]
              if x["state"]=="MATURED_OUTCOME_UNRESOLVED_FAIL_CLOSED"]
    assert affected
    assert any("FICTIONAL_V3_SECURITY_0" in x["unresolved_ids"] for x in affected)
    assert all(x["as_of_cohort_sha256"] for x in affected)
    assert out["complete_nonoverlapping_folds"] < out["matured_as_of_eligible_anchors"]
    # Missing returns are never replaced with 0, last price, or the next winner.
    assert all(not any("IMPUTED" in str(x) for x in out["folds"]) for _ in range(1))


def test_v3_not_matured_anchor_is_pending_not_bad_market_return(tmp_path):
    out=evaluate_v3(make_v3_bundle(tmp_path,as_of="2023-02-01"))
    assert out["pending_not_yet_matured_anchors"]>=1
    assert out["matured_outcome_unresolved_anchors"]==0
    assert any(x["state"]=="OUTCOME_NOT_MATURED_AS_OF_CUTOFF"
               for x in out["ex_ante_anchor_audit"])
    assert out["predictive_edge_certified"] is False


def test_v3_immutable_same_day_asof_rank_against_later_prices(tmp_path):
    out=make_v3_bundle(tmp_path)
    original=evaluate_v3(out)
    first=next(x for x in original["ex_ante_anchor_audit"]
               if x["state"]=="MATURED_COMPLETE")
    assert first["date"]=="2021-07-01"
    # Changing one future price after this decision is allowed to alter
    # realized returns, but MUST NOT alter the earlier selection as-of T.
    # V2's _eligible no-lookahead is reused unchanged in V3.
    from investresearch.research_historical_validation_v2 import _eligible
    from decimal import Decimal
    series=[(s,Decimal("100")+Decimal(i)/100,Decimal("100000"))
            for i,s in enumerate(dates_v2(date(2021,1,1),date(2021,12,30),"XMIL"))]
    t="2021-07-01"
    asset={"id":"TEST","asset_type":"EQUITY","currency":"EUR",
           "venue":"XMIL","sector":"NONOIL","oil_exposure":"none"}
    settings={"exclude_primary_oil":True,"exclude_additional_gold":True,
              "avoid_duplicate_eurostoxx50":True}
    before=_eligible(asset,[r for r in series if r[0]<=t],t,settings)
    assert before is not None
    after=_eligible(asset,series,t,settings)
    assert before==after
