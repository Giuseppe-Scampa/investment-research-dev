"""Tiingo Starter Free: no real network, credentials or account data."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from investresearch.market_calendar import session
from investresearch.research_tiingo_personal_collect import collect_one
from investresearch.research_bundle import build_bundle


def data():
    today=datetime.now(timezone.utc).date()
    days=[today-timedelta(days=i) for i in range(190,-1,-1)]
    days=[d for d in days if d.year==2026 and session(d,"XNAS")]
    assert len(days)>=61
    events=[]
    for i,d in enumerate(days):
        p=100+i*.1
        events.append({"date":d.isoformat()+"T00:00:00Z",
            "open":p,"high":p*1.01,"low":p*.99,"close":p,
            "adjOpen":p*.99,"adjHigh":p*1.01*.99,
            "adjLow":p*.99*.99,"adjClose":p*.99,
            "volume":100000,"adjVolume":100000,
            "divCash":.1 if i==len(days)-25 else 0,
            "splitFactor":1})
    return json.dumps(events).encode()


class Reply:
    def __init__(self, request, raw):
        self.url=request.full_url
        self.raw=raw
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def geturl(self):
        return self.url
    def read(self, cap):
        return self.raw[:cap]


class Opener:
    def __init__(self, raw):
        self.raw=raw
        self.calls=[]
    def open(self, request, timeout):
        assert timeout==18
        self.calls.append(request)
        return Reply(request,self.raw)


def options(tmp_path,opener):
    return {
        "symbol":"AAPL","isin":"US0378331005","venue":"XNAS",
        "instrument_name":"SYNTHETIC ONLY US EQUITY INPUT",
        "asset_type":"EQUITY","sector":"Synthetic technology","oil_exposure":"none",
        "output":tmp_path/"source","repo_root":tmp_path/"repo",
        "api_token":"SYNTHETIC_NOT_REAL_SECRET",
        "personal_rights_ack":True,"identity_review_ack":True,
        "opener":opener,
    }


def test_private_tiingo_one_request_with_header_secret_and_bundle(tmp_path):
    opener=Opener(data())
    audit=collect_one(**options(tmp_path,opener))
    assert audit["source_sessions"]>=61
    assert audit["trade_ready"] is False
    assert len(opener.calls)==1
    req=opener.calls[0]
    assert "SYNTHETIC_NOT_REAL_SECRET" not in req.full_url
    assert req.get_header("Authorization")=="Token SYNTHETIC_NOT_REAL_SECRET"
    assert "/tiingo/daily/AAPL/prices?" in req.full_url
    spec=json.loads((tmp_path/"source/BUNDLE_INPUT_SPEC.json").read_text())
    assert "SYNTHETIC_NOT_REAL_SECRET" not in json.dumps(spec)
    assert len(spec["assets"])==1
    bundle=build_bundle(spec,tmp_path/"out")
    assert bundle["assets"][0]["prices"]["price_basis"]==(
        "TIINGO_PROVIDER_SPLIT_ADJUSTED_CLOSE_NOT_TOTAL_RETURN")
    assert audit["eod_source_sha256"]==hashlib.sha256(data()).hexdigest()


@pytest.mark.parametrize("change,pattern", [
    ("terms","terms"),("identity","identity"),("demo","token"),
    ("missing_key","token"),("venue","venue"),("oil","Ethical"),
])
def test_no_call_before_rights_mapping_and_token_gate(tmp_path,change,pattern):
    opener=Opener(data());kw=options(tmp_path,opener)
    if change=="terms":kw["personal_rights_ack"]=False
    if change=="identity":kw["identity_review_ack"]=False
    if change=="demo":kw["api_token"]="demo"
    if change=="missing_key":kw["api_token"]=None
    if change=="venue":kw["venue"]="XETR"
    if change=="oil":kw["oil_exposure"]="not_checked"
    with pytest.raises(ValueError,match=pattern):
        collect_one(**kw)
    assert not opener.calls
    assert not kw["output"].exists()


def test_provider_account_error_never_written_or_returned(tmp_path):
    opener=Opener(b'{"detail":"Permission denied"}')
    kw=options(tmp_path,opener)
    with pytest.raises(ValueError,match="bounded list"):
        collect_one(**kw)
    assert len(opener.calls)==1
    assert not kw["output"].exists()


def test_live_starter_collection_is_disabled_before_api_or_file_io(tmp_path):
    fake=Opener(data())
    args=options(tmp_path,fake)
    args["opener"]=None
    with pytest.raises(ValueError,match="TIINGO_STARTER_PERSISTENT_STORAGE_NOT_PERMITTED"):
        collect_one(**args)
    assert not fake.calls
    assert not args["output"].exists()
