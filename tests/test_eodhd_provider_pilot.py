"""EODHD free/evaluation feed: synthetic fixtures, NEVER market price artefacts."""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from investresearch.market_calendar import session
from investresearch.research_eodhd_pilot import (
    assess, parse_eod, parse_splits, parse_dividends, run_demo, SCHEMA,
)


AS_OF = date(2026, 11, 5)
RETRIEVED = datetime(2026, 11, 5, 20, tzinfo=timezone.utc)


def fixture_data(*, with_split=False):
    days = [
        date(2026, 7, 1)+timedelta(days=i)
        for i in range((AS_OF-date(2026, 7, 1)).days+1)
    ]
    days = [d for d in days if session(d, "XNAS")]
    assert len(days) >= 61
    splitdate = days[-30]
    eod = []
    for i, day in enumerate(days):
        base = 200 + i*.2
        if with_split and day >= splitdate:
            base = base / 2
        eod.append({"date": day.isoformat(), "open": base,
                    "high": base*1.012, "low": base*.988,
                    "close": base, "adjusted_close": base*.995,
                    "volume": 100000+i*100})
    splits = ([{"date": splitdate.isoformat(),
                "split": "2.000000/1.000000"}] if with_split else [])
    dividends = [{
        "date": days[-40].isoformat(), "value": .25,
        "unadjustedValue": .25, "currency": "USD",
        "recordDate": None, "declarationDate": None,
        "paymentDate": None, "period": "Quarterly",
    }]
    return (json.dumps(eod).encode(), json.dumps(splits).encode(),
            json.dumps(dividends).encode())


def test_live_schema_parser_and_split_adjustment_of_synthetic_61_bars():
    raw, sp, dv = fixture_data(with_split=True)
    out = assess(raw, sp, dv, as_of=AS_OF, retrieved_at_utc=RETRIEVED)
    assert out["schema_version"] == SCHEMA
    assert out["last_61_contiguous_nasdaq_sessions"]
    assert out["split_events_61"] == 1
    assert out["dividend_events_61"] == 1
    assert out["market_price_score"] is None
    assert not out["license_validated_for_private_production"]
    assert not out["cross_provider_actions_reconciled"]
    assert out["demo_data_not_trade_ready"]


def test_nosplit_source_does_not_pretend_fully_adjusted_ohlc():
    raw, sp, dv = fixture_data()
    out = assess(raw, sp, dv, as_of=AS_OF, retrieved_at_utc=RETRIEVED)
    assert out["ohlc_basis"] == "RAW_AS_TRADED"
    assert out["historical_volume_basis"] == "SPLIT_ADJUSTED_PROVIDER_DEFINITION"
    assert out["adjusted_close_basis"] == "PROVIDER_SPLIT_AND_DIVIDEND_ADJUSTED"
    assert out["split_events_61"] == 0


@pytest.mark.parametrize("defect", ["schema", "duplicate", "future",
                                    "zero", "nonfinite", "ohlc", "empty"])
def test_price_source_malformed_fails_closed(defect):
    raw, _, _ = fixture_data()
    items = json.loads(raw)
    if defect == "schema":
        del items[0]["adjusted_close"]
    elif defect == "duplicate":
        items.append(copy.deepcopy(items[0]))
    elif defect == "future":
        items[-1]["date"] = "2026-11-06"
    elif defect == "zero":
        items[-1]["close"] = 0
    elif defect == "nonfinite":
        items[-1]["open"] = "NaN"
    elif defect == "ohlc":
        items[-1]["high"] = 0.01
    elif defect == "empty":
        items = []
    with pytest.raises(ValueError):
        parse_eod(json.dumps(items).encode(), as_of=AS_OF)


def test_duplicate_json_and_error_object_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        parse_eod(b'[{"date":"2026-10-01","date":"2026-10-02"}]', as_of=AS_OF)
    with pytest.raises(ValueError, match="array"):
        parse_eod(b'{"message":"too many API calls"}', as_of=AS_OF)


def test_splits_reversals_and_dividends_are_explicitly_parsed():
    parsed = parse_splits(
        b'[{"date":"2026-09-01","split":"3.000000/2.000000"},'
        b'{"date":"2026-10-01","split":"1.000000/8.000000"}]',
        as_of=AS_OF)
    assert [str(x["ratio"]) for x in parsed] == ["1.5", "0.125"]
    with pytest.raises(ValueError, match="Duplicate"):
        parse_splits(
            b'[{"date":"2026-09-01","split":"2/1"},'
            b'{"date":"2026-09-01","split":"2/1"}]', as_of=AS_OF)
    with pytest.raises(ValueError, match="currency"):
        parse_dividends(
            b'[{"date":"2026-08-01","value":1,"unadjustedValue":1,"currency":"EUR"}]',
            as_of=AS_OF)


def test_forced_missing_session_and_snapshot_order_rejected():
    raw, spl, div = fixture_data()
    rows = json.loads(raw)
    rows.pop(-8)
    with pytest.raises(ValueError, match="Missing/extra"):
        assess(json.dumps(rows).encode(), spl, div,
               as_of=AS_OF, retrieved_at_utc=RETRIEVED)
    with pytest.raises(ValueError, match="Retrieval timestamp"):
        assess(raw, spl, div, as_of=AS_OF,
               retrieved_at_utc=datetime(2026, 11, 4, tzinfo=timezone.utc))


def test_offline_provider_invocation_is_one_explicit_bounded_demo_triplet():
    eod, splits, div = fixture_data()
    class Reply:
        def __init__(self, url, body):
            self.url, self.body = url, body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def geturl(self):
            return self.url
        def read(self, n):
            assert n < 200_000
            return self.body[:n]
    class FakeOpener:
        def __init__(self):
            self.calls = []
        def open(self, request, timeout):
            assert timeout <= 18
            self.calls.append(request.full_url)
            kind = request.full_url.split("/api/")[1].split("/")[0]
            return Reply(request.full_url, {"eod":eod,"splits":splits,"div":div}[kind])
    o = FakeOpener()
    assert run_demo(as_of=AS_OF, live_confirm=True, opener=o)["available_eod_sessions"] >= 61
    assert len(o.calls) == 3
    assert all("api_token=demo" in u and "fmt=json" in u for u in o.calls)
    with pytest.raises(ValueError, match="explicit"):
        run_demo(as_of=AS_OF, opener=o)
