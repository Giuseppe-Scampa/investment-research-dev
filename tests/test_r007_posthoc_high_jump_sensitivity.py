"""Strictly post-hoc, source-vintage-locked 15% jump sensitivity regression.

All test returns FICTIONAL, and cannot be promoted to market alpha.
"""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import inspect_posthoc_high_jump_sensitivity as m


def test_posthoc_scope_immutable_but_not_confirmatory():
    p,hash_=m.sensitivity_policy()
    assert len(hash_)==64
    assert p["posthoc_descriptive_only"] is True
    assert p["first_actual_source_experiment_already_seen"] is True
    assert p["first_source_missingness_outcome_already_seen"] is True
    assert p["never_use_as_confirmatory_test"] is True
    assert p["acceptance"]["allow_conclusion_about_true_alpha"] is False
    assert p["source_original_SHA256"]==m.original_source.FIRST_OBSERVED_SOURCE_SHA256 | {
        "companies":m.original_source.FIRST_OBSERVED_SOURCE_SHA256["members"]
    } if False else p["source_original_SHA256"]


def _fold(t):
    return {"decision_date":t,"selected_net":.01,
            "same_K_uniform_random_expected_net":.005,
            "same_K_excess_net":.005,"ic":.1}


def _strict(months,reasons):
    return {
        "calendar_months":months,
        "count":{"matured_complete":1,"matured_unresolved":1},
        "folds":[_fold("2024-01-01")],
        "as_of_anchor_audit":[{
            "state":m.CENSORED,
            "unresolved_by_id":reasons,
            "decision_date":"2024-08-01",
        }],
        "mean_selected_net":.01,
        "mean_same_K_excess_net":.005,
    }


def test_new_proxy_is_separately_labelled_with_unmodified_original_folds(monkeypatch):
    monkeypatch.setattr(m,"EXPECTED_ORIGINAL_COUNTS",{1:(1,1),3:(1,1),6:(1,1)})
    monkeypatch.setattr(m,"_reprice_original_censored",
                        lambda row,universe,policy,settings: _fold(row["decision_date"]))
    out=m._summarize([
        _strict(1,{"FAKE_A":m.JUMP}),
        _strict(3,{"FAKE_A":m.JUMP}),
        _strict(6,{"FAKE_A":m.JUMP}),
    ],{},{"costs":{}},{})
    assert len(out)==3
    assert all(x["original_strict_completed"]==1 for x in out)
    assert all(x["additional_previously_censored_folds_with_vendor_proxy"]==1
               for x in out)
    assert all(x["descriptive_total_folds_with_vendor_adjusted_proxy"]==2
               for x in out)
    assert all(x["can_change_frozen_research_acceptance"] is False
               for x in out)


def test_missing_exchange_session_is_never_filled_from_jump_sensitivity(monkeypatch):
    monkeypatch.setattr(m,"EXPECTED_ORIGINAL_COUNTS",{1:(1,1),3:(1,1),6:(1,1)})
    monkeypatch.setattr(m,"_reprice_original_censored",
                        lambda *args:pytest.fail("Must not reprice missing market bars"))
    out=m._summarize([
        _strict(1,{"FAKE_A":m.GAP}),
        _strict(3,{"FAKE_A":m.GAP}),
        _strict(6,{"FAKE_A":m.GAP}),
    ],{},{"costs":{}},{})
    assert all(x["still_unresolved_missing_original_sessions"]==1 for x in out)
    assert all(x["additional_previously_censored_folds_with_vendor_proxy"]==0 for x in out)
