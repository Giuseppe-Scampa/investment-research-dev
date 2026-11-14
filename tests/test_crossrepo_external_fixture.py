"""True EXTERNAL branch integration test, input is 100% fabricated, never real market."""
from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

import pytest

from investresearch.research_screen import screen
from investresearch.tactical_research import build_tactical
from investresearch.research_risk import analyze_risk
from investresearch.tax_engine import FiscalRegistry
from investresearch.cli import ROOT


def _generator():
    # CI-only fixture from tools/; do not treat as an approved source provider.
    return runpy.run_path(str(ROOT/"tools/generate_crossrepo_external_fixture.py"))["generate"]


def test_two_mock_issuers_reach_live_codepath_and_remain_no_trade(tmp_path):
    source = _generator()(tmp_path/"synthetic_fixture_two_fake_us_prices")
    result = screen(source)
    assert result["dataset_mode"] == "EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE"
    assert result["universe_size"] == 2
    assert result["ranked_count"] == 2
    assert all(r["trade_ready"] is False for r in result["results"])
    assert all(r["name"].startswith("NOT_MARKET_DATA_") for r in result["results"])
    fiscal = FiscalRegistry.load(ROOT/"config/fiscal/rules_2026.json")
    tactical = build_tactical(result, fiscal_registry=fiscal)
    assert tactical["research_eligible_count"] == 2
    assert len(tactical["research_priorities_by_type"]) == 2
    assert not tactical["trade_ready"]
    risk = analyze_risk(source, result, tactical)
    assert risk["pairs_count"] == 1
    assert risk["comparable_pairs"] == 1
    assert not risk["portfolio_approved"]
    assert risk["dataset_manifest_sha256"] == hashlib.sha256(
        (source/"manifest.json").read_bytes()).hexdigest()


def test_fixture_generator_cannot_overwrite_or_write_unmarked_path(tmp_path):
    generator = _generator()
    with pytest.raises(ValueError, match="NEW synthetic_fixture"):
        generator(tmp_path/"unmarked")
    assert not (tmp_path/"unmarked").exists()
    out = tmp_path/"synthetic_fixture_safe"
    generator(out)
    with pytest.raises(ValueError, match="NEW synthetic_fixture"):
        generator(out)
