"""R-008 risk: historical correlations are evidence diagnostics, never forecasts."""
from __future__ import annotations

import copy
import json

import pytest

from investresearch.cli import ROOT
from investresearch.research_bundle import SYNTHETIC, EXTERNAL
from investresearch.research_screen import screen
from investresearch.tactical_research import build_tactical
from investresearch.tax_engine import FiscalRegistry
from investresearch.research_risk import (
    VERSION, _correlation, analyze_risk, write_risk,
)
from investresearch.research_cli import main

BUNDLE = ROOT/"data/research/demo"


def pair():
    screened = screen(BUNDLE)
    tactical = build_tactical(screened, fiscal_registry=FiscalRegistry.load(
        ROOT/"config/fiscal/rules_2026.json"))
    return screened, tactical


def test_synthetic_full_bundle_risk_is_audit_only(tmp_path):
    screening, tactical = pair()
    out = analyze_risk(BUNDLE, screening, tactical)
    assert out["schema_version"] == VERSION
    assert out["dataset_mode"] == SYNTHETIC
    assert out["risk_scope"] == "SYNTHETIC_DIAGNOSTIC_ONLY"
    assert out["selected_count"] <= 12
    assert out["pairs_count"] == out["selected_count"]*(out["selected_count"]-1)//2
    assert out["trade_ready"] is False and out["portfolio_approved"] is False
    coverage = out["price_coverage_by_asset_type"]
    assert sum(x["submitted"] for x in coverage.values()) == screening["universe_size"]
    assert sum(x["market_screened"] for x in coverage.values()) == screening["ranked_count"]
    assert all(x["submitted"] == x["market_screened"] + x["not_screened"]
               for x in coverage.values())
    assert isinstance(out["screening_warning_counts"], dict)
    assert out["tactical_sha256"]
    for row in out["pairs"]:
        assert row["trade_ready"] is False
        assert row["return_observations"] <= 60
        v = row["correlation_eur_eod_historical"]
        assert v is None or -1 <= v <= 1
        assert "CLOSE_TO_CLOSE_HISTORICAL_NOT_EXPECTED_RETURN" in row["notes"]
    write_risk(out, tmp_path/"demo", repo_root=ROOT)
    assert json.loads((tmp_path/"demo/BLOCK_B_RISK.json").read_text()) == out


@pytest.mark.parametrize("change", ["screen_hash", "screen_mode", "tactical_hash", "tactical_mode"])
def test_risk_refuses_unpaired_inputs(change):
    s, t = pair()
    if change == "screen_hash":
        s["dataset_manifest_sha256"] = "f"*64
    if change == "screen_mode":
        s["dataset_mode"] = EXTERNAL
    if change == "tactical_hash":
        t["screening_sha256"] = "f"*64
    if change == "tactical_mode":
        t["dataset_mode"] = EXTERNAL
    with pytest.raises(ValueError, match="Risk input"):
        analyze_risk(BUNDLE, s, t)


def test_pairwise_correlation_constant_undefined_and_aligned():
    assert _correlation(list(range(20)), list(range(20))) == 1
    assert _correlation(list(range(20)), list(reversed(range(20)))) == -1
    assert _correlation([3]*20, list(range(20))) is None
    with pytest.raises(ValueError, match="Insufficient"):
        _correlation([1, 2], [1, 2])


def test_external_market_risk_output_is_private_only(tmp_path):
    s, t = pair()
    result = analyze_risk(BUNDLE, s, t)
    result["dataset_mode"] = EXTERNAL
    with pytest.raises(ValueError, match="private"):
        write_risk(result, ROOT/"reports/generated/leakage-probe", repo_root=ROOT)
    assert not (ROOT/"reports/generated/leakage-probe/BLOCK_B_RISK.json").exists()


def test_cli_produces_real_synthetic_source_risk(tmp_path, capsys):
    main(["risk", "--bundle", str(BUNDLE), "--output", str(tmp_path/"cli")])
    out = json.loads((tmp_path/"cli/BLOCK_B_RISK.json").read_text())
    assert out["risk_scope"] == "SYNTHETIC_DIAGNOSTIC_ONLY"
    assert "NO expected returns" in capsys.readouterr().out


def test_correlation_matrix_and_illustrative_stress_are_source_bound():
    screening, tactical=pair()
    out=analyze_risk(BUNDLE,screening,tactical)
    stress=out["illustrative_portfolio_stress"]
    assert stress["schema_version"]=="r008-source-bound-illustrative-portfolio-stress-v1"
    assert stress["correlation_matrix_ids"]==out["selected_ids"]
    assert stress["identities"]==out["selected_ids"][:3]
    n=out["selected_count"]
    assert len(stress["correlation_matrix"])==n
    assert all(len(row)==n for row in stress["correlation_matrix"])
    for p in out["pairs"]:
        i=out["selected_ids"].index(p["id_a"])
        j=out["selected_ids"].index(p["id_b"])
        assert stress["correlation_matrix"][i][j]==p["correlation_eur_eod_historical"]
        assert stress["correlation_matrix"][j][i]==p["correlation_eur_eod_historical"]
    assert stress["synthetic_fictional_data"] is True
    assert stress["actual_holdings_weights_used"] is False
    assert stress["risk_approved"] is False
    assert stress["trade_ready"] is False
    assert stress["diversification_or_downside_forecast_verified"] is False
    assert stress["status"] in (
        "SYNTHETIC_EQUAL_WEIGHT_STRESS_ONLY",
        "INSUFFICIENT_ALIGNED_EUR_EOD_SESSIONS",
        "INSUFFICIENT_CANDIDATES",
    )
    if stress["status"]=="SYNTHETIC_EQUAL_WEIGHT_STRESS_ONLY":
        assert stress["common_return_observations"]>=20
        assert 0<=stress["historical_max_drawdown_pct"]<=100
        assert stress["historical_annualized_volatility_pct"]>=0
        assert stress["parallel_shock_minus_10_pct"]==-10
        assert stress["parallel_shock_minus_20_pct"]==-20


def test_portfolio_stress_fails_closed_if_common_series_missing():
    from investresearch.research_portfolio_stress import build_portfolio_stress
    from decimal import Decimal
    one={"observations":{"2026-01-02":Decimal("100"),"2026-01-05":Decimal("101")}}
    other={"observations":{"2026-04-01":Decimal("100"),"2026-04-02":Decimal("99")}}
    pair={"id_a":"A","id_b":"B","correlation_eur_eod_historical":None}
    out=build_portfolio_stress(["A","B"],{"A":one,"B":other},[pair],synthetic=False)
    assert out["status"]=="INSUFFICIENT_ALIGNED_EUR_EOD_SESSIONS"
    assert out["historical_max_drawdown_pct"] is None
    assert out["parallel_shock_minus_10_pct"] is None
    assert out["trade_ready"] is False


def test_portfolio_stress_fixed_shock_is_not_expected_loss_or_weight_recommendation():
    from investresearch.research_portfolio_stress import build_portfolio_stress
    from decimal import Decimal
    from datetime import date,timedelta
    dates=[(date(2026,1,2)+timedelta(days=n)).isoformat() for n in range(24)]
    first={"observations":{d:Decimal("100")+Decimal(i) for i,d in enumerate(dates)}}
    second={"observations":{d:Decimal("100")-Decimal(i)/2 for i,d in enumerate(dates)}}
    result=build_portfolio_stress(["A","B"],{"A":first,"B":second},
        [{"id_a":"A","id_b":"B","correlation_eur_eod_historical":-1.0}],synthetic=False)
    assert result["status"]=="SOURCE_BOUND_HISTORICAL_STRESS_UNVERIFIED_NOT_TRADE_READY"
    assert result["common_return_observations"]==23
    assert result["historical_worst_day_pct"] is not None
    assert result["parallel_shock_minus_20_pct"]==-20.0
    assert result["portfolio_optimality_asserted"] is False
    assert result["actual_holdings_weights_used"] is False
    assert result["trade_ready"] is False
