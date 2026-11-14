"""Static P0 source-inventory guard: discovered HTML URLs are NOT admitted market data."""
from __future__ import annotations

import json
from pathlib import Path

CATALOG=(Path(__file__).resolve().parents[1] /
    "config/pit/p0_official_historical_source_candidates_2026-11-14.json")


def test_all_four_original_historical_index_candidates_remain_fail_closed():
    raw=CATALOG.read_bytes()
    doc=json.loads(raw)
    assert doc["schema_version"]=="P0_OFFICIAL_MEMBERSHIP_SOURCE_CANDIDATE_CATALOG_V1"
    assert doc["as_of_research_date"]=="2026-11-14"
    assert doc["trade_ready"] is False
    assert doc["not_a_price_feed"] is True
    assert doc["no_original_source_bytes_in_git"] is True
    assert doc["all_source_rights_unverified_for_automated_research"] is True
    entries=doc["sources"]
    assert len(entries)==4
    assert {x["market"] for x in entries}=={"USA","ITALY","GERMANY","FRANCE"}
    for x in entries:
        assert x["url"].startswith("https://")
        assert x["candidate_snapshot_as_of"].startswith("2021-")
        assert x["rights_for_intended_use"]=="UNVERIFIED"
        assert x["downloaded_source_bytes"] is False
        assert x["security_identity_complete"] is False
        assert x["membership_certificate"] is False
        assert x["historical_availability_evidence"]
        assert x["blocking_note"]


def test_cac_no_change_notice_never_admitted_as_complete_roster():
    doc=json.loads(CATALOG.read_text())
    france=next(x for x in doc["sources"] if x["market"]=="FRANCE")
    assert france["role"]=="DATED_CHANGE_NOTICE_NOT_FULL_BASELINE"
    assert france["candidate_snapshot_actual_effective_date_verified"] is True
    assert france["membership_certificate"] is False


def test_italian_july_report_does_not_backdate_to_first_july_decision():
    doc=json.loads(CATALOG.read_text())
    italy=next(x for x in doc["sources"] if x["market"]=="ITALY")
    assert italy["candidate_snapshot_as_of"]=="2021-06-30"
    assert "July 30 report is future" in italy["blocking_note"]
