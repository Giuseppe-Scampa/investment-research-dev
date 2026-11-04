"""R-006/R-007/R-008: deterministic funnel with no fabricated market coverage.

Synthetic 250-item report here is constructed ONLY for testing selection
logic. It is not built from 250 independently observed company histories.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from investresearch.cli import ROOT
from investresearch.research_bundle import SYNTHETIC, EXTERNAL
from investresearch.research_funnel import (
    ALLOWED_REVIEW, DILIGENCE_VERSION, DEFAULT_POLICY, VERSION,
    build_funnel, write_funnel)
from investresearch.research_cli import main
from investresearch.research_screen import screen

BUNDLE = ROOT / "data/research/demo"


def simulated_large_report():
    demo = screen(BUNDLE)
    ranked = [r for r in demo["results"] if r["market_score"] is not None]
    assert len(ranked) == 5
    rows = []
    for i in range(250):
        r = copy.deepcopy(ranked[i % 5])
        r["id"] = f"SYNTHETIC_{i:04d}"
        r["name"] = f"Invented instrument {i:04d}"
        r["sector"] = f"TEST_SECTOR_{i % 10:02d}"
        r["market_score"] = round(90 - (i % 100)*0.5, 2)
        r["market_rank"] = None
        rows.append(r)
    demo["results"] = rows
    demo["universe_size"] = len(rows)
    demo["ranked_count"] = len(rows)
    return demo


def reviewed_funnel_item(report, uid):
    return {
        "id": uid, "status": ALLOWED_REVIEW, "as_of": report["as_of"],
        "upside_case": "A hypothetical upside case requiring verification.",
        "downside_case": "A downside case including adverse market scenarios.",
        "counter_thesis": "A competing explanation challenges the price trend.",
        "valuation_limitations": "No documented comparable valuation is present.",
        "source_evidence": [{
            "source_url": "https://research.example.test/public/mock-issuer-filing",
            "published_date": report["as_of"],
            "sha256": None,
        }],
    }


def diligence_for(report, deep):
    return {
        "schema_version": DILIGENCE_VERSION,
        "as_of": report["as_of"],
        "dataset_manifest_sha256": report["dataset_manifest_sha256"],
        "reviews": [reviewed_funnel_item(report, x["id"]) for x in deep],
    }


def test_small_real_demo_never_claims_global_funnel_or_fills_quota():
    report = screen(BUNDLE)
    f = build_funnel(report)
    assert f["schema_version"] == VERSION
    assert f["input_universe_count"] == 7
    assert f["research_eligible_count"] == 5
    assert f["status"] == "INSUFFICIENT_RESEARCH_UNIVERSE_NO_SHORTLIST"
    assert not f["stage_1_pool"]
    assert not f["stage_2_deep_dive"]
    assert not f["stage_3_provisional_finalists"]
    assert f["trade_ready"] is False
    by_id = {r["id"]:r["reasons"] for r in f["exclusion_reasons"]}
    assert "HARD_CONSTRAINT" in by_id["DEMO_OIL"]
    assert "NO_VALID_MARKET_RESEARCH_SCORE" in by_id["DEMO_SHORT"]


def test_large_synthetic_funnel_deterministic_with_sector_caps_and_no_finalists():
    report = simulated_large_report()
    first = build_funnel(report)
    second = build_funnel(copy.deepcopy(report))
    assert first == second
    assert first["input_universe_count"] == 250
    assert first["research_eligible_count"] == 250
    assert len(first["stage_1_pool"]) == 40
    assert len(first["stage_2_deep_dive"]) == 6
    assert len(first["stage_3_provisional_finalists"]) == 0
    assert first["status"] == "AWAITING_INDEPENDENT_DILIGENCE_NO_FINALISTS"
    assert all(r["trade_ready"] is False for r in first["stage_1_pool"])
    assert all(r["trade_ready"] is False for r in first["stage_2_deep_dive"])
    assert set(x["id"] for x in first["stage_2_deep_dive"]).issubset(
        {x["id"] for x in first["stage_1_pool"]})
    from collections import Counter
    assert max(Counter(r["sector"] for r in first["stage_1_pool"]).values()) <= 10
    assert max(Counter(r["sector"] for r in first["stage_2_deep_dive"]).values()) <= 2
    ordered = sorted(first["stage_1_pool"], key=lambda r:(-r["market_score"],r["id"]))
    assert [r["id"] for r in first["stage_1_pool"]] == [r["id"] for r in ordered]


def test_diligence_can_produce_only_provisional_nontrade_finalists():
    report = simulated_large_report()
    stage2 = build_funnel(report)["stage_2_deep_dive"]
    evidence = diligence_for(report, stage2)
    a = build_funnel(report, diligence=evidence)
    assert a["status"] == "PROVISIONAL_RESEARCH_FINALISTS_NOT_TRADE_READY"
    assert len(a["stage_3_provisional_finalists"]) == 3
    assert [x["id"] for x in a["stage_3_provisional_finalists"]] == [
        x["id"] for x in stage2[:3]]
    assert a["trade_ready"] is False
    assert all(not x["trade_ready"] for x in a["stage_3_provisional_finalists"])
    assert a["manual_diligence_status"] == "MANUAL_ASSERTIONS_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert all(x["diligence"]["status"] == ALLOWED_REVIEW
               for x in a["stage_3_provisional_finalists"])


@pytest.mark.parametrize("tamper,match", [
    (lambda d: d.update(as_of="2026-11-03"), "as_of does not match"),
    (lambda d: d.update(dataset_manifest_sha256="f"*64), "different research bundle"),
    (lambda d: d["reviews"][0].update(id="NOT_A_CANDIDATE"), "unselected"),
    (lambda d: d["reviews"][0].update(status="TRADE_READY"), "trade readiness"),
    (lambda d: d["reviews"][0].update(as_of="2026-11-05"), "after research"),
    (lambda d: d["reviews"][0].update(counter_thesis="x"), "substantive"),
    (lambda d: d["reviews"][0]["source_evidence"][0].update(published_date="2026-11-05"),
     "not published"),
    (lambda d: d["reviews"][0]["source_evidence"][0].update(source_url="http://unsafe.test"),
     "HTTPS"),
    (lambda d: d["reviews"][0]["source_evidence"][0].update(sha256="bad"),
     "SHA256"),
])
def test_diligence_fail_closed_for_unverified_future_or_invalid_assertions(tamper,match):
    report = simulated_large_report()
    stage2 = build_funnel(report)["stage_2_deep_dive"]
    d = diligence_for(report, stage2)
    tamper(d)
    with pytest.raises(ValueError,match=match):
        build_funnel(report,diligence=d)


def test_funnel_filters_blocked_unknown_score_missing_history_and_duplicates():
    report = simulated_large_report()
    report["results"][0]["blocking_constraints"] = ["oil"]
    report["results"][1]["market_score"] = None
    report["results"][2]["history_quality"]["verified"] = False
    report["results"][3]["market_score"] = float("nan")
    result = build_funnel(report)
    by_id = {r["id"]:r["reasons"] for r in result["exclusion_reasons"]}
    assert "HARD_CONSTRAINT" in by_id["SYNTHETIC_0000"]
    assert "MISSING_OR_INVALID_SCORE" in by_id["SYNTHETIC_0001"]
    assert "UNVERIFIED_61_SESSION_HISTORY" in by_id["SYNTHETIC_0002"]
    assert "MISSING_OR_INVALID_SCORE" in by_id["SYNTHETIC_0003"]
    report["results"][5]["id"] = report["results"][4]["id"]
    with pytest.raises(ValueError,match="Duplicate"):
        build_funnel(report)


def test_real_research_requires_isin_provenance_and_status_not_synthetic():
    report = simulated_large_report()
    report["dataset_mode"] = EXTERNAL
    for r in report["results"]:
        r["status"] = "RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY"
        r["isin"] = ""
        r["price_source_url"] = ""
    result = build_funnel(report)
    assert result["research_eligible_count"] == 0
    assert "UNVERIFIED_ISIN" in result["exclusion_reasons"][0]["reasons"]
    assert "UNVERIFIED_PRICE_SOURCE" in result["exclusion_reasons"][0]["reasons"]
    assert not result["stage_1_pool"]


@pytest.mark.parametrize("field,value", [
    ("research_pool", 29), ("deep_dive", 8), ("finalists", 4),
    ("min_universe", 199), ("research_pool", True),
])
def test_funnel_policy_limits_cannot_be_used_to_fake_coverage(field,value):
    p = dict(DEFAULT_POLICY)
    p[field] = value
    with pytest.raises(ValueError, match="Funnel"):
        build_funnel(screen(BUNDLE),policy=p)


def test_funnel_outputs_reproducible_and_private_boundary(tmp_path):
    report=simulated_large_report()
    result=build_funnel(report)
    out=write_funnel(result,tmp_path/"demo",repo_root=tmp_path/"repo")
    saved={p.name:p.read_bytes() for p in out.iterdir()}
    assert set(saved)=={"RESEARCH_FUNNEL.json","RESEARCH_FUNNEL.csv","RESEARCH_FUNNEL.md"}
    write_funnel(build_funnel(report),out,repo_root=tmp_path/"repo")
    assert saved=={p.name:p.read_bytes() for p in out.iterdir()}
    data=json.loads((out/"RESEARCH_FUNNEL.json").read_text())
    assert data["status"] == "AWAITING_INDEPENDENT_DILIGENCE_NO_FINALISTS"
    external=copy.deepcopy(result)
    external["dataset_mode"]=EXTERNAL
    with pytest.raises(ValueError,match="ignored data/private"):
        write_funnel(external,tmp_path/"repo"/"reports"/"generated",repo_root=tmp_path/"repo")
    private=write_funnel(external,tmp_path/"repo"/"data"/"private"/"funnel",repo_root=tmp_path/"repo")
    assert (private/"RESEARCH_FUNNEL.json").exists()


def test_cli_demo_funnel_end_to_end_no_invented_finalists(tmp_path,capsys):
    out=tmp_path/"funnel"
    main(["funnel","--bundle",str(BUNDLE),"--output",str(out)])
    report=json.loads((out/"RESEARCH_FUNNEL.json").read_text())
    assert report["status"]=="INSUFFICIENT_RESEARCH_UNIVERSE_NO_SHORTLIST"
    assert len(report["stage_3_provisional_finalists"])==0
    assert "NOT trade-ready" in capsys.readouterr().out
