"""P0 original lifecycle retention and private historical-source readiness.

ALL price and instrument inputs in this test are FICTIONAL, not market data.
"""
from __future__ import annotations

from datetime import date
import copy
import json
from pathlib import Path

import pytest

from investresearch.historical_calendar_v2 import dates_v2
from investresearch.research_bundle import SYNTHETIC, build_bundle, load_bundle
from investresearch.research_historical_source_readiness import (
    audit_historical_source_readiness, write_readiness,
)
from investresearch.research_historical_validation_v2 import preregistered_anchors
from investresearch.research_historical_validation_v3 import v3_protocol
from investresearch.research_cli import main


def _fake_bundle(tmp_path, *, unknown_second=True, omit_future=False):
    dates = dates_v2(date(2021, 1, 4), date(2022, 6, 30), "XMIL")
    anchor = preregistered_anchors(["XMIL"], v3_protocol()[0])[0]
    future = dates_v2(date.fromisoformat(anchor), date(2021, 10, 30), "XMIL")
    remove = future[11]
    assets = []
    for i in range(2):
        raw = tmp_path / f"FICTIONAL_PRICES_{i}.csv"
        rows = ["date,close,volume"]
        for j, d in enumerate(dates):
            if omit_future and i == 0 and d == remove:
                continue
            rows.append(f"{d},{100+i*5+j*.003:.6f},100000")
        raw.write_text("\n".join(rows) + "\n")
        asset = {
            "id":f"FICTIONAL_{i}","name":f"FAKE_{i}",
            "asset_type":"EQUITY","sector":"FAKE_NON_OIL",
            "venue":"XMIL","currency":"EUR","oil_exposure":"none",
            "prices_source":{"provider":"SYNTHETIC_PRICES","path":str(raw)},
        }
        if i == 0 or not unknown_second:
            asset["listing_date"] = "2021-01-04"
        assets.append(asset)
    spec = {"mode":SYNTHETIC,"as_of":"2022-06-30","assets":assets}
    path = tmp_path / "FICTIONAL_BUNDLE"
    build_bundle(spec,path)
    return spec,path


def test_original_lifecycle_preserved_and_missing_date_never_inferred(tmp_path):
    _,path = _fake_bundle(tmp_path)
    _,items,_,_ = load_bundle(path)
    assert items[0][0]["listing_date"] == "2021-01-04"
    assert "listing_date" not in items[1][0]
    assert "delisted_date" not in items[0][0]
    report = audit_historical_source_readiness(path)
    assert report["unknown_listing_date_count"] == 1
    assert report["member_anchor_combinations_without_any_listing_vintage"] > 0
    assert report["member_anchor_combinations_with_complete_61_day_history"] > 0
    assert report["source_mode"] == SYNTHETIC
    assert report["research_readiness"].startswith("BLOCKED")
    assert report["original_exchange_prices_independently_verified"] is False
    assert report["predictive_edge_certified"] is False
    assert report["trade_ready"] is False


def test_matured_future_gap_cannot_be_promoted(tmp_path):
    _,path = _fake_bundle(tmp_path,unknown_second=False,omit_future=True)
    report = audit_historical_source_readiness(path)
    assert report["member_anchor_combinations_with_matured_unresolved_31_day_path"] >= 1
    assert report["member_anchor_combinations_with_matured_complete_31_day_path"] >= 1
    assert report["statistical_performance_calculated"] is False


@pytest.mark.parametrize("bad",["not-a-date","2022-13-20","2026/10/31",123,"2022-06-01T00:00:00"])
def test_invalid_listing_date_fails_during_import(tmp_path,bad):
    _,path = _fake_bundle(tmp_path)
    spec = {"mode":SYNTHETIC,"as_of":"2022-06-30","assets":[{
        "id":"FICTIONAL_BAD","name":"FAKE","venue":"XMIL","currency":"EUR",
        "prices_source":{"provider":"SYNTHETIC_PRICES",
                         "path":str(tmp_path/"FICTIONAL_PRICES_0.csv")},
        "listing_date":bad,
    }]}
    with pytest.raises((ValueError,TypeError)):
        build_bundle(spec,tmp_path/"NEW_REJECTED_BUNDLE")


def test_delisted_before_listing_is_rejected(tmp_path):
    _,_ = _fake_bundle(tmp_path)
    spec = {"mode":SYNTHETIC,"as_of":"2022-06-30","assets":[{
        "id":"FICTIONAL_BAD","name":"FAKE","venue":"XMIL","currency":"EUR",
        "prices_source":{"provider":"SYNTHETIC_PRICES",
                         "path":str(tmp_path/"FICTIONAL_PRICES_0.csv")},
        "listing_date":"2021-10-01","delisted_date":"2021-09-30",
    }]}
    with pytest.raises(ValueError,match="Delisting precedes listing"):
        build_bundle(spec,tmp_path/"NEW_REJECTED_BUNDLE")


def test_original_source_byte_tamper_blocks_readiness(tmp_path):
    _,path = _fake_bundle(tmp_path)
    price = path/"prices/FICTIONAL_0.csv"
    price.write_bytes(price.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="hash mismatch"):
        audit_historical_source_readiness(path)


def test_private_only_writer_and_cli_do_not_change_v3(tmp_path,capsys):
    _,path = _fake_bundle(tmp_path)
    report = audit_historical_source_readiness(path)
    private = tmp_path/"data/private"
    private.mkdir(parents=True)
    output=private/"READINESS.json"
    result=write_readiness(report,output,repo_root=tmp_path)
    assert result.is_file()
    loaded=json.loads(result.read_text())
    assert not any(k in loaded for k in ("asset_ids","prices","selected_top2","portfolio_return"))
    with pytest.raises(ValueError,match="NEW"):
        write_readiness(report,output,repo_root=tmp_path)
    with pytest.raises(ValueError,match="private"):
        write_readiness(report,tmp_path/"PUBLIC.json",repo_root=tmp_path)
    cli_file=private/"READINESS_CLI.json"
    main(["historical-source-readiness","--bundle",str(path),
          "--output",str(cli_file)])
    assert json.loads(cli_file.read_text())["source_manifest_sha256"] == report["source_manifest_sha256"]
    assert "no alpha or orders" in capsys.readouterr().out
