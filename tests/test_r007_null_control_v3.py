"""Synthetic Gaussian no-alpha calibration checks, V3. No historical inputs."""
from investresearch.research_negative_control_v3 import run_null_worlds_v3
from investresearch.research_historical_validation_v3 import v3_protocol


def test_v3_same_k_null_is_separate_and_never_returns_market_edge():
    report=run_null_worlds_v3(worlds=4)
    policy,sha=v3_protocol()
    assert report["schema_version"]=="V3_V3_SAME_K_RANDOM_WALK_NULL_CALIBRATION"
    assert report["preregistered_protocol_sha256"]==sha
    assert report["primary_benchmark"]==policy["comparisons"]["primary_benchmark"]
    assert report["worlds_completed"]==4
    assert report["full_preregistered_world_count_completed"] is False
    assert report["null_calibration_passed"] is False
    assert report["predictive_edge_certified"] is False
    assert report["trade_ready"] is False
    assert report["not_a_validated_external_pit_universe"] is True
    assert abs(report["mean_null_excess_vs_same_K_exact_expected"])<0.1
    assert (report["mean_null_excess_vs_N_leg_universe_DESCRIPTIVE"]-
            report["mean_null_excess_vs_same_K_exact_expected"])>0.01
