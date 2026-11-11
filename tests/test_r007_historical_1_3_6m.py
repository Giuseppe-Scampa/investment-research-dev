"""1, 3 and 6 calendar-month ex-ante historical REPLAY tests.

All records are FICTIONAL synthetic prices, never financial evidence.
"""
from datetime import date
import json
import runpy
from pathlib import Path

import pytest

from investresearch.research_historical_1_3_6m import (
    add_calendar_months, replay_protocol, evaluate_historical_1_3_6,
    _venue_dates, FROZEN_GIT_BLOB,
)

MAKE=runpy.run_path(str(Path(__file__).with_name(
    "test_r007_historical_validation_v3.py")))["make_v3_bundle"]


@pytest.mark.parametrize(("d","months","expect"),[
    (date(2024,1,31),1,date(2024,2,29)),
    (date(2025,1,31),1,date(2025,2,28)),
    (date(2024,8,31),6,date(2025,2,28)),
    (date(2024,11,30),3,date(2025,2,28)),
    (date(2023,12,31),6,date(2024,6,30)),
])
def test_exact_month_anniversary_is_not_21_63_126_bars(d,months,expect):
    assert add_calendar_months(d,months)==expect


def test_registration_untouched_and_separate_from_30_session_v3(tmp_path,monkeypatch):
    import investresearch.research_historical_1_3_6m as module
    p,sha=replay_protocol()
    assert len(sha)==64
    assert p["schedule"]["horizons_calendar_months"]==[1,3,6]
    assert p["costs"]["commission_fraction_each_side"]==.0019
    assert p["frozen_model"]["portfolio_k"]==2
    assert p["replay_only"] is True
    assert FROZEN_GIT_BLOB=="05a63cc0906c782b2909031b0bb1fe0d09ad76e4"
    old=json.loads(module.PROTOCOL.read_text())
    old["comparators"]["primary"]="FAVORABLE_N_LEG_MINIMUM_FEES"
    altered=tmp_path/"changed_after_observed_results.json"
    altered.write_text(json.dumps(old))
    monkeypatch.setattr(module,"PROTOCOL",altered)
    with pytest.raises(ValueError,match="preregistration"):
        module.replay_protocol()


def test_multi_market_venue_exit_is_on_after_real_month_anniversary():
    t="2024-03-28"
    values={}
    for venue in ("XNYS","XMIL","XETR","XPAR"):
        entry,exit_=_venue_dates(t,venue,3)
        assert entry>t
        assert date.fromisoformat(exit_)>=add_calendar_months(
            date.fromisoformat(entry),3)
        values[venue]=(entry,exit_)
    assert len({pair[0] for pair in values.values()})>=2


def test_full_time_travel_replay_uses_existing_rank_1_3_6_calendar_months(tmp_path):
    out=evaluate_historical_1_3_6(MAKE(tmp_path))
    assert out["schema_version"]=="V3_AS_OF_1_3_6_CALENDAR_MONTH_REPLAY_V1"
    assert out["registered_protocol_git_blob"]==FROZEN_GIT_BLOB
    assert out["data_mode"]=="SYNTHETIC_DEMONSTRATION_NOT_MARKET_DATA"
    assert out["as_of_anchor_count"]>=30
    assert [h["calendar_months"] for h in out["independent_horizon_results"]]==[1,3,6]
    counts=[h["count"]["matured_complete"] for h in out["independent_horizon_results"]]
    assert counts[0]>counts[1]>counts[2]>=4
    assert counts[2]<30
    assert out["horizons_share_selection_and_are_statistically_correlated"] is True
    assert out["point_in_time_delisted_and_failed_membership_verified"] is False
    assert out["predictive_edge_certified"] is False
    assert out["trade_ready"] is False
    snapshots={}
    for h in out["independent_horizon_results"]:
        assert h["count"]["matured_unresolved"]==0
        assert h["minimum_independent_fold_and_complete_data_gate"] is False or h["calendar_months"]==1
        assert h["random_K_portfolio_trials"]==10000
        assert h["primary_paired_fold_bootstrap_CI_95"] is not None
        prev_end=None
        for f in h["folds"]:
            assert len(f["selected_ids"])==2
            assert f["selected_net"]-f["same_K_uniform_random_expected_net"] == pytest.approx(
                f["same_K_excess_net"],abs=2.1e-8)
            assert f["selected_cash_pnl_eur"]==pytest.approx(
                10000*f["selected_net"],abs=.01)
            assert len(f["selected_entry_exit"])==2
            assert len(f["spread_sensitivity_DESCRIPTIVE_ONLY"])==4
            assert f["spread_sensitivity_DESCRIPTIVE_ONLY"][0][
                "same_K_excess_net"]==pytest.approx(f["same_K_excess_net"],abs=2.1e-8)
            for row in f["selected_entry_exit"]:
                assert row["entry_date"]>f["decision_date"]
                assert date.fromisoformat(row["exit_date"])>=add_calendar_months(
                    date.fromisoformat(row["entry_date"]),h["calendar_months"])
            if prev_end:
                assert f["decision_date"]>prev_end
            prev_end=f["planned_latest_exit"]
            current=f["decision_date"]
            if current in snapshots:
                assert f["selected_ids"]==snapshots[current]
            else:
                snapshots[current]=f["selected_ids"]
        assert h["confirmatory_alpha_validation"] is False


@pytest.mark.parametrize("mode",["gap","crash"])
def test_missing_or_crashed_future_does_not_select_only_profitable_cohorts(tmp_path,mode):
    params={"remove_future":mode=="gap","crash_future":mode=="crash"}
    out=evaluate_historical_1_3_6(MAKE(tmp_path,**params))
    problem=[]
    for horizon in out["independent_horizon_results"]:
        problem += [r for r in horizon["as_of_anchor_audit"]
                    if r["state"]=="MATURED_UNRESOLVED_DO_NOT_DISCARD_MEMBERS"]
        if horizon["count"]["matured_unresolved"]>0:
            assert horizon["minimum_independent_fold_and_complete_data_gate"] is False
    assert problem
    assert any("FICTIONAL_V3_SECURITY_0" in row["unresolved_by_id"] for row in problem)
    assert out["predictive_edge_certified"] is False


def test_as_of_cutoff_preserves_pending_horizon_without_future_returns(tmp_path):
    out=evaluate_historical_1_3_6(MAKE(tmp_path,as_of="2023-03-01"))
    assert any(h["count"]["future_pending"]>=1
               for h in out["independent_horizon_results"])
    assert all(not h["confirmatory_alpha_validation"]
               for h in out["independent_horizon_results"])
