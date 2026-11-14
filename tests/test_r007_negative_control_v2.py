"""Small smoke of the same V2 code path; full 1000 worlds in CI separate job."""
from investresearch.research_negative_control_v2 import run_null_worlds


def test_v2_full_score_on_three_independent_random_walk_null_worlds():
    report=run_null_worlds(worlds=3)
    assert report["worlds_completed"]==3
    assert report["worlds_preregistered"]==1000
    assert report["independent_null_folds_per_world"]==30
    assert report["synthetic_random_walk_assets_per_world"]==30
    assert report["bootstrap_resamples_per_world"]==10000
    assert report["random_portfolio_trials_per_world"]==10000
    assert report["historical_returns_verified"] is False
    assert report["predictive_edge_certified"] is False
    assert report["full_preregistered_world_count_completed"] is False
    assert report["null_calibration_passed"] is False
    assert report["warning_N_leg_benchmark_minimum_fee_bias"] is True
    assert 0<=report["false_positive_rate_observed"]<=1
