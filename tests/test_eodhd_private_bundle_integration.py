"""EODHD personal-source importer regression: ALL inputs are synthetic fixtures.

The EXTERNAL bundle mode exercises the parser's real-data branch but these
test rows are invented; they are NOT published quote evidence or investments.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta

import pytest

from investresearch.market_calendar import session
from investresearch.research_bundle import EXTERNAL, build_bundle, load_bundle
from investresearch.research_eodhd_local import (
    ATTESTATION, MAPPING, PROVIDER,
)
from investresearch.research_screen import screen

AS_OF = date(2026, 11, 5)
SYMBOL = "FAKE.XETRA"
ISIN = "DE0006231004"


def _write(tmp_path, name, obj):
    p = tmp_path/name
    p.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")
    return p


def source_spec(tmp_path, *, with_split=True):
    days = [date(2026, 7, 1)+timedelta(days=i)
            for i in range((AS_OF-date(2026, 7, 1)).days+1)]
    days = [x for x in days if session(x, "XETR")]
    assert len(days) >= 61
    split_day = days[-32]
    bars = []
    for i, day in enumerate(days):
        b = 120 + i*0.07
        if with_split and day >= split_day:
            b /= 2
        bars.append({
            "date": day.isoformat(), "open": b,
            "high": b*1.015, "low": b*.985, "close": b,
            "adjusted_close": b*.99, "volume": 250_000,
        })
    splits = ([{"date": split_day.isoformat(), "split": "2/1"}]
              if with_split else [])
    dividends = [{
        "date": days[-40].isoformat(), "value": .25,
        "unadjustedValue": .25, "currency": "EUR",
    }]
    eod = _write(tmp_path, "eod.json", bars)
    split = _write(tmp_path, "split.json", splits)
    div = _write(tmp_path, "div.json", dividends)
    stamp = "2026-11-05T18:00:00+00:00"

    def file_meta(path, provider, kind):
        return {
            "path": str(path), "provider": provider,
            "source_url": f"https://eodhd.com/api/{kind}/{SYMBOL}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "retrieved_at_utc": stamp,
        }

    price = {
        **file_meta(eod, PROVIDER, "eod"), "symbol": SYMBOL,
        "isin": ISIN, "venue": "XETR", "currency": "EUR",
        "usage_attestation": ATTESTATION,
        "identity_evidence_status": MAPPING,
        "splits_source": file_meta(split, "EODHD_PERSONAL_SPLITS", "splits"),
        "dividends_source": file_meta(div, "EODHD_PERSONAL_DIVIDENDS", "div"),
    }
    spec = {
        "as_of": AS_OF.isoformat(), "mode": EXTERNAL,
        "assets": [{
            "id": "SYNTHETIC_EODHD_ADAPTER_TEST",
            "name": "SYNTHETIC PRICE PAYLOAD; NEVER A REAL QUOTATION",
            "isin": ISIN, "venue": "XETR", "currency": "EUR",
            "asset_type": "EQUITY", "sector": "Synthetic sector",
            "oil_exposure": "none", "prices_source": price,
        }],
    }
    return spec


def test_external_importer_split_price_volume_basis_and_market_quality(tmp_path):
    spec = source_spec(tmp_path, with_split=True)
    out = tmp_path/"bundle"
    manifest = build_bundle(spec, out)
    assert "EODHD_PERSONAL_SPLITS" in manifest["source_kinds"]
    assert "EODHD_PERSONAL_DIVIDENDS" in manifest["source_kinds"]
    assert manifest["assets"][0]["prices"]["split_dates"]
    assert (manifest["assets"][0]["prices"]["price_basis"]
            == "EODHD_PROVIDER_SPLIT_ADJUSTED_CLOSE_NOT_TOTAL_RETURN")
    loaded, items, fx, ev = load_bundle(out)
    assert len(items[0][1]) >= 61
    closes = [float(x["close"]) for x in items[0][1]]
    # The synthetic 2:1 share split must NOT cause a false 50% daily crash.
    assert max(abs(closes[i]/closes[i-1]-1) for i in range(1,len(closes))) < .01
    screened = screen(out)
    row = screened["results"][0]
    assert "SPLITS_APPLIED_FROM_SAME_PROVIDER_NOT_INDEPENDENTLY_VERIFIED" in row["warnings"]
    assert "UNADJUSTED_SPLIT_REQUIRES_CORPORATE_ACTION_REVIEW" not in row["warnings"]
    assert row["history_quality"]["verified"] is True
    assert not row["trade_ready"]
    assert row["market_score"] is not None
    assert "USER_ASSERTED_PERSONAL_LOCAL_ONLY_NOT_INDEPENDENTLY_LICENSED" in str(manifest)


@pytest.mark.parametrize("mutation,expected", [
    ("rights", "rights attestation"),
    ("identity", "ISIN/venue mapping"),
    ("isin", "mapping"),
    ("venue", "exchange suffix"),
    ("source_url", "price URL"),
    ("split_source_url", "URL/symbol"),
    ("hash", "SHA-256"),
    ("dividend_ccy", "currency"),
    ("no_61", "61"),
])
def test_reject_invalid_personal_source_and_corporate_actions(tmp_path, mutation, expected):
    spec = source_spec(tmp_path)
    price = spec["assets"][0]["prices_source"]
    if mutation == "rights":
        price["usage_attestation"] = "AGREE"
    elif mutation == "identity":
        price["identity_evidence_status"] = "NOT_REVIEWED"
    elif mutation == "isin":
        price["isin"] = "US0378331005"
    elif mutation == "venue":
        price["symbol"] = "FAKE.US"
    elif mutation == "source_url":
        price["source_url"] = "https://evil.invalid/api/eod/FAKE.XETRA"
    elif mutation == "split_source_url":
        price["splits_source"]["source_url"] = "https://eodhd.com/api/splits/OTHER.XETRA"
    elif mutation == "hash":
        price["splits_source"]["sha256"] = "0"*64
    elif mutation == "dividend_ccy":
        f = tmp_path/"div.json"
        f.write_text('[{"date":"2026-10-15","value":1,"unadjustedValue":1,"currency":"USD"}]')
        price["dividends_source"]["sha256"] = hashlib.sha256(f.read_bytes()).hexdigest()
    elif mutation == "no_61":
        f = tmp_path/"eod.json"
        f.write_text(json.dumps(json.loads(f.read_text())[-40:]))
        price["sha256"] = hashlib.sha256(f.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match=expected):
        build_bundle(spec, tmp_path/"built")


def test_external_source_requires_real_provenance_hash_without_fake_backfill(tmp_path):
    spec = source_spec(tmp_path, with_split=False)
    p = spec["assets"][0]["prices_source"]
    del p["sha256"]
    with pytest.raises(ValueError, match="SHA-256"):
        build_bundle(spec, tmp_path/"built")


def test_cross_asset_source_prohibits_incorrect_venue_currency_or_bad_symbol(tmp_path):
    spec = source_spec(tmp_path)
    p = spec["assets"][0]["prices_source"]
    p["symbol"] = "FAKE.XETRA?api_token=demo"
    with pytest.raises(ValueError, match="symbol"):
        build_bundle(spec, tmp_path/"built")
