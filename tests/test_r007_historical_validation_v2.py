"""Protocol V2: multi-year historic data correctness, no 2026 calendar leakage."""
from datetime import date,timedelta
from pathlib import Path
from statistics import mean
import hashlib
import json
import math

import pytest

from investresearch.historical_calendar_v2 import dates_v2
from investresearch.research_bundle import SYNTHETIC,build_bundle
from investresearch.research_historical_validation_v2 import (
    v2_protocol,preregistered_anchors,evaluate_v2,approximate_power,
    _eligible,
)


def make_fixture(tmp_path,*,assets=24,regime="mixed"):
    sessions=dates_v2(date(2020,12,1),date(2026,7,15),"XMIL")
    entries=[]
    for k in range(assets):
        original=tmp_path/f"FICTIONAL_LONG_HORIZON_{k}.csv"
        rows=["date,close,volume"]
        for j,day in enumerate(sessions):
            drift=(k%9-4)*.00022
            base=100+k*4
            price=base*(1+drift*j)+1.4*math.sin(j/16+k)
            if regime=="reversal" and day>="2024-02-01":
                price=base*(1+drift*600)-.012*base*(j-800)/100
            price=max(2.,price)
            rows.append(f"{day},{price:.6f},{300000+k*1000}")
        original.write_text("\n".join(rows)+"\n")
        entries.append({
            "id":f"TEST_ONLY_FOLD_ASSET_{k}",
            "name":f"FICTIONAL_{k}_EQUITY",
            "isin":"","asset_type":"EQUITY",
            "currency":"EUR","venue":"XMIL",
            "sector":"FICTIONAL_NONOIL","oil_exposure":"none",
            "prices_source":{"provider":"SYNTHETIC_PRICES",
                             "path":str(original)},
        })
    out=tmp_path/"BUNDLE_LONG_V2"
    build_bundle({"mode":SYNTHETIC,"as_of":"2026-07-15","assets":entries},out)
    return out


def test_protocol_v2_has_independent_multi_year_anchors_and_not_modified_v1():
    policy,hash_value=v2_protocol()
    assert len(hash_value)==64
    assert policy["calendar"]["required_version"]=="4.13.1"
    assert policy["comparisons"]["negative_control_random_walk_worlds"]==1000
    assert len(preregistered_anchors(["XMIL"],policy))>=35
    assert len(preregistered_anchors(["XETR","XMIL","XNYS"],policy))>=35
    assert policy["cohort"]["minimum_independent_folds_for_predictive_evidence"]==30
    from investresearch.market_calendar import session
    with pytest.raises(ValueError):
        session(date(2024,2,1),"XMIL")


def test_long_horizon_real_pipeline_on_synthetic_is_necessarily_non_predictive(tmp_path):
    bundle=make_fixture(tmp_path)
    result=evaluate_v2(bundle)
    assert result["schema_version"]=="V3_LONG_HORIZON_BACKTEST_V2"
    assert result["status"]=="SYNTHETIC_NO_MARKET_EVIDENCE"
    assert result["planned_decision_anchors"]>=35
    assert result["complete_nonoverlapping_folds"]>=30
    assert result["random_portfolio_trials"]==10000
    assert result["confidence_interval_95_excess"] is not None
    assert result["confidence_interval_95_ic"] is not None
    assert all(len(f["selected_ids"])==2 and len(f["bottom_ids"])==2
               for f in result["folds"])
    assert all(f["eligible"]==24 for f in result["folds"])
    assert result["historical_corporate_actions_independently_verified"] is False
    assert result["historical_point_in_time_universe_independently_verified"] is False
    assert result["random_walk_false_positive_rate_calibrated"] is False
    assert result["predictive_edge_certified"] is False
    assert result["trade_ready"] is False


def test_v2_score_not_changed_by_future_append_and_future_column_canary():
    asset={"id":"TEST_A","asset_type":"EQUITY","venue":"XMIL",
           "currency":"EUR","sector":"NONOIL","oil_exposure":"none"}
    dates=dates_v2(date(2023,7,1),date(2024,12,31),"XMIL")
    from decimal import Decimal
    rows=[(d,Decimal("100")+Decimal(i)/100,Decimal("300000"))
          for i,d in enumerate(dates)]
    target="2024-04-02"
    setting={"exclude_primary_oil":True,"exclude_additional_gold":True,
             "avoid_duplicate_eurostoxx50":True}
    x=_eligible(asset,[r for r in rows if r[0]<=target],target,setting)
    assert x is not None
    with_future=_eligible(asset,rows,target,setting)
    assert x==with_future


def test_power_calibration_is_explicit_and_does_not_claim_edge():
    result=approximate_power()
    assert len(result)==3*5*4
    zero=[x for x in result if x["IC"]==0.0]
    assert all(0.045<=v["two_sided_power_approx"]<=0.055 for v in zero)
    weak=[x for x in result if x["IC"]==0.05 and x["assets"]==30]
    assert weak[0]["two_sided_power_approx"]<.80
