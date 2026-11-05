"""Tiingo Starter personal-source parser and external bundle adapter.

All records are SYNTHETIC FIXTURES, though the EXTERNAL code path is tested.
No provider account, broker positions, market-data redistribution or API calls.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date,timedelta

import pytest

from investresearch.research_tiingo_local import (
    parse_tiingo, normalize_private_tiingo, PROVIDER, ATTESTATION, MAPPING)
from investresearch.market_calendar import session
from investresearch.research_bundle import build_bundle, EXTERNAL, load_bundle
from investresearch.research_screen import screen

ASOF = date(2026, 11, 5)


def make_source(tmp_path, *, split=True):
    start = date(2026, 7, 1)
    days = [start+timedelta(days=i) for i in range((ASOF-start).days+1)]
    days = [d for d in days if session(d, "XNAS")]
    assert len(days) >= 61
    splitdate = days[-30]
    bars = []
    for i,d in enumerate(days):
        close = 140+i*.08
        if split and d >= splitdate:
            close/=2
        bars.append({
            "date":d.isoformat()+"T00:00:00.000Z",
            "open":close, "high":close*1.01, "low":close*.99,
            "close":close, "volume":120_000,
            "adjOpen":close*.99, "adjHigh":close*1.01*.99,
            "adjLow":close*.99*.99, "adjClose":close*.99,
            "adjVolume":240_000,
            "divCash":.1 if d==days[-45] else 0,
            "splitFactor":2 if split and d==splitdate else 1,
        })
    raw = tmp_path/"tiingo_source.json"
    raw.write_text(json.dumps(bars),encoding="utf-8")
    source = {
        "provider":PROVIDER, "source_url":"https://api.tiingo.com/tiingo/daily/FAKE/prices",
        "path":str(raw), "sha256":hashlib.sha256(raw.read_bytes()).hexdigest(),
        "retrieved_at_utc":"2026-11-05T19:00:00+00:00",
        "usage_attestation":ATTESTATION,
        "identity_evidence_status":MAPPING,
        "symbol":"FAKE",
        "isin":"US0378331005", "venue":"XNAS", "currency":"USD",
    }
    asset = {
        "id":"FICTIONAL_TIINGO_ADAPTER_TEST", "name":"TEST-NOT-REAL-TIINGO-PRICE",
        "isin":"US0378331005", "asset_type":"EQUITY",
        "sector":"Synthetic technology", "venue":"XNAS", "currency":"USD",
        "oil_exposure":"none",
        "prices_source":source,
    }
    return raw,asset


def test_split_and_dividend_fields_integrate_private_source_manifest(tmp_path):
    raw,asset = make_source(tmp_path)
    spec = {"mode":EXTERNAL,"as_of":ASOF.isoformat(),"assets":[asset]}
    bundle = tmp_path/"private"
    manifest = build_bundle(spec,bundle)
    meta = manifest["assets"][0]["prices"]
    assert meta["price_basis"] == "TIINGO_PROVIDER_SPLIT_ADJUSTED_CLOSE_NOT_TOTAL_RETURN"
    assert len(meta["split_dates"]) == 1
    assert meta["source_dividend_event_count"] == 1
    assert meta["corporate_actions_verified_by_independent_source"] is False
    source,records,fx,events = load_bundle(bundle)
    closes = [float(row["close"]) for row in records[0][1]]
    assert max(abs(closes[i]/closes[i-1]-1) for i in range(1,len(closes))) < .01
    screened = screen(bundle)
    r = screened["results"][0]
    assert r["market_score"] is None  # USD input without same-day ECB FX
    assert "MISSING_ECB_FX" in r["warnings"]
    assert not r["trade_ready"]


@pytest.mark.parametrize("change,match", [
    ("rights","terms"),
    ("mapping","terms"),
    ("isin","mapping"),
    ("url","URL"),
    ("currency","mapping"),
    ("rows","61"),
    ("hash","SHA-256"),
])
def test_tiingo_rejects_missing_price_rights_and_identity_evidence(tmp_path,change,match):
    raw,asset=make_source(tmp_path)
    p=asset["prices_source"]
    if change=="rights": p["usage_attestation"]="not accepted"
    if change=="mapping": p["identity_evidence_status"]="unknown"
    if change=="isin": p["isin"]="GB00B15KXQ89"
    if change=="url": p["source_url"]="https://api.tiingo.com/tiingo/daily/WRONG/prices"
    if change=="currency": p["currency"]="EUR"
    if change=="rows":
        raw.write_text(json.dumps(json.loads(raw.read_text())[-40:]))
        p["sha256"]=hashlib.sha256(raw.read_bytes()).hexdigest()
    if change=="hash": p["sha256"]="f"*64
    with pytest.raises(ValueError,match=match):
        build_bundle({"mode":EXTERNAL,"as_of":ASOF.isoformat(),
                      "assets":[asset]},tmp_path/"bundle")


def test_tiingo_parser_rejects_duplicate_session_and_invalid_adjustment(tmp_path):
    raw,_=make_source(tmp_path)
    rows=json.loads(raw.read_text())
    rows += [copy.deepcopy(rows[-1])]
    with pytest.raises(ValueError,match="Duplicate Tiingo"):
        parse_tiingo(json.dumps(rows).encode(),as_of=ASOF)
    rows.pop()
    rows[-1]["adjClose"]="NaN"
    with pytest.raises(ValueError,match="nonfinite|invalid|Nonpositive"):
        parse_tiingo(json.dumps(rows).encode(),as_of=ASOF)
    rows[-1]["adjClose"]=100
    rows[-1]["date"]="2026-11-06T00:00:00Z"
    with pytest.raises(ValueError,match="Future"):
        parse_tiingo(json.dumps(rows).encode(),as_of=ASOF)


def test_tiingo_requires_utc_and_verified_exchange(tmp_path):
    raw,asset=make_source(tmp_path)
    asset["prices_source"]["retrieved_at_utc"]="2026-11-05T20:00:00+01:00"
    with pytest.raises(ValueError,match="UTC"):
        build_bundle({"mode":EXTERNAL,"as_of":ASOF.isoformat(),
                      "assets":[asset]},tmp_path/"bundle")
