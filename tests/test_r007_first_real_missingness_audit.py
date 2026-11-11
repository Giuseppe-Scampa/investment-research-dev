"""First real-source missingness audit: aggregate-only, fail closed on changed data."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import audit_first_real_source_missingness as m


def _fixture():
    def h(months,counts,missing_by_fold):
        a=[{"state":"MATURED_UNRESOLVED_DO_NOT_DISCARD_MEMBERS",
            "unresolved_by_id":reasons}
           for reasons in missing_by_fold]
        return {"calendar_months":months,
                "count":{"matured_complete":counts,
                         "matured_unresolved":len(a)},
                "as_of_anchor_audit":a}
    return [
        h(1,2,[{"FAKE_X":m.REASONS[0],"FAKE_Y":m.REASONS[1]},
               {"FAKE_X":m.REASONS[0]}]),
        h(3,1,[{"FAKE_X":m.REASONS[1]}]),
        h(6,1,[{"FAKE_X":m.REASONS[0]}]),
    ]


def test_diagnostic_counts_are_frozen_cohort_aggregate_only():
    out=m.reason_counts(_fixture())
    assert len(out)==3
    assert out[0]["incomplete_folds_with_missing_venue_session"]==2
    assert out[0]["incomplete_folds_with_unverified_ge15pct_jump"]==1
    assert out[0]["incomplete_folds_with_both_types"]==1
    assert out[0]["missing_session_asset_fold_events"]==2
    assert out[0]["distinct_affected_research_ids_never_disclosed"]==2
    assert "FAKE_X" not in str(out)
    assert all(x["retrospective_complete_case_returns_promoted_to_alpha"] is False
               for x in out)


@pytest.mark.parametrize("attack",["missing_reasons","new_reason","dropped_fold","unregistered_month"])
def test_matured_missing_no_silent_rewrite(attack):
    x=_fixture()
    if attack=="missing_reasons":
        x[0]["as_of_anchor_audit"][0]["unresolved_by_id"]={}
    elif attack=="new_reason":
        x[0]["as_of_anchor_audit"][0]["unresolved_by_id"]["FAKE_X"]="FAKE_DELISTED_PAYOUT"
    elif attack=="dropped_fold":
        x[0]["count"]["matured_unresolved"]=100
    elif attack=="unregistered_month":
        x[0]["calendar_months"]=12
    with pytest.raises(ValueError):
        m.reason_counts(x)
