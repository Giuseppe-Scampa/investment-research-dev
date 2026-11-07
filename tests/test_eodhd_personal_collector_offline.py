"""Private EODHD collector: no network, no real token, no third-party prices."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from investresearch.market_calendar import session
from investresearch.research_bundle import build_bundle, EXTERNAL
from investresearch.research_eodhd_personal_collect import collect_one

ISIN = "DE0006231004"
SYMBOL = "FIXTURE.XETRA"


def fixtures():
    end = datetime.now(timezone.utc).date()
    days = [end-timedelta(days=i) for i in range(180, -1, -1)]
    days = [day for day in days if session(day,"XETR")]
    rows = [{
        "date": day.isoformat(), "open": 100+i*.05,
        "high": 101+i*.05, "low": 99+i*.05, "close":100+i*.05,
        "adjusted_close":(100+i*.05)*.996, "volume": 150000,
    } for i,day in enumerate(days)]
    dividends = [{"date":days[-30].isoformat(),"value":.1,
                  "unadjustedValue":.1,"currency":"EUR"}]
    return (json.dumps(rows).encode(), b"[]", json.dumps(dividends).encode())


class Reply:
    def __init__(self, url, payload):
        self.url, self.payload = url, payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.url
    def read(self,n):
        return self.payload[:n]


class FakeOpener:
    def __init__(self, fixtures):
        self.fixture = dict(zip(("eod","splits","div"),fixtures))
        self.urls = []
    def open(self, req, timeout):
        assert timeout <= 18
        url = req.full_url
        self.urls.append(url)
        kind = url.split("/api/")[1].split("/")[0]
        return Reply(url, self.fixture[kind])


def params(tmp_path, fake):
    return {
        "symbol": SYMBOL, "isin": ISIN, "venue":"XETR", "currency":"EUR",
        "instrument_name": "SYNTHETIC PRIVATE SOURCE TEST",
        "asset_type":"EQUITY", "sector":"Synthetic industry",
        "oil_exposure":"none", "output":tmp_path/"sources",
        "repo_root":tmp_path/"repo", "api_token":"SYNTHETIC_TEST_KEY_DO_NOT_USE",
        "personal_rights_ack":True,"identity_review_ack":True,
        "opener":fake,
    }


def test_personal_collector_three_calls_and_real_local_bundle_import(tmp_path):
    fake = FakeOpener(fixtures())
    report = collect_one(**params(tmp_path,fake))
    assert len(fake.urls) == 3
    assert report["source_eod_sessions"] >= 61
    assert report["market_data_is_private"] is True
    assert report["trade_ready"] is False
    spec = json.loads((tmp_path/"sources/BUNDLE_INPUT_SPEC.json").read_text())
    assert spec["mode"] == EXTERNAL
    assert spec["assets"][0]["isin"] == ISIN
    assert "api_token" not in json.dumps(spec)
    assert "SYNTHETIC_TEST_KEY" not in json.dumps(spec)
    bundle = build_bundle(spec, tmp_path/"private-bundle")
    assert bundle["assets"][0]["prices"]["price_basis"] == (
        "EODHD_PROVIDER_SPLIT_ADJUSTED_CLOSE_NOT_TOTAL_RETURN")
    assert not bundle["assets"][0]["prices"]["corporate_actions_verified_by_independent_source"]
    for filename in ("eod.json", "splits.json", "dividends.json",
                     "SOURCE_INTAKE_AUDIT.json", "BUNDLE_INPUT_SPEC.json"):
        assert (tmp_path/"sources"/filename).is_file()


@pytest.mark.parametrize("mutation,match", [
    ("terms","terms acknowledgement"),
    ("identity","identity review"),
    ("demo","not demo"),
    ("no_token","token required"),
    ("venue","symbol/venue"),
    ("oil","Ethical oil"),
])
def test_personal_collector_refuses_unauthorised_source_calls(tmp_path, mutation, match):
    fake = FakeOpener(fixtures())
    p = params(tmp_path, fake)
    if mutation == "terms":
        p["personal_rights_ack"]=False
    elif mutation == "identity":
        p["identity_review_ack"]=False
    elif mutation == "demo":
        p["api_token"]="demo"
    elif mutation == "no_token":
        p["api_token"]=None
    elif mutation == "venue":
        p["venue"]="XNAS"
    elif mutation == "oil":
        p["oil_exposure"]="NOT_EVALUATED"
    with pytest.raises(ValueError,match=match):
        collect_one(**p)
    assert fake.urls == []
    assert not p["output"].exists()


def test_provider_entitlement_error_cannot_leak_token(tmp_path):
    fake = FakeOpener((b'{"message":"rate limited"}',b"[]",b"[]"))
    p = params(tmp_path, fake)
    with pytest.raises(ValueError, match="JSON array"):
        collect_one(**p)
    assert len(fake.urls)==3
    assert not p["output"].exists()
