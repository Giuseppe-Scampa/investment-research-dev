"""Tiingo free-tier batch: 2 independent fake-symbol payloads, NEVER API calls."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from investresearch.market_calendar import session
from investresearch.research_tiingo_batch import collect_batch, VERSION
from investresearch.research_bundle import build_bundle


def _bars(base, trend):
    today=datetime.now(timezone.utc).date()
    days=[today-timedelta(days=i) for i in range(190,-1,-1)]
    dates=[d for d in days if d.year==2026 and session(d,"XNAS")]
    assert len(dates)>=61
    result=[]
    for index,d in enumerate(dates):
        p=base+trend*index+(index%4)*.02
        result.append({
            "date":d.isoformat()+"T00:00:00Z",
            "open":p,"high":p*1.01,"low":p*.99,"close":p,
            "adjOpen":p,"adjHigh":p*1.01,"adjLow":p*.99,
            "adjClose":p,"volume":100000,"adjVolume":100000,
            "divCash":0,"splitFactor":1,
        })
    return json.dumps(result).encode()


class Reply:
    def __init__(self,url,payload):
        self.url,self.payload=url,payload
    def __enter__(self):
        return self
    def __exit__(self,*a):
        return False
    def geturl(self):
        return self.url
    def read(self,cap):
        return self.payload[:cap]


class Fake:
    def __init__(self):
        self.urls=[]
        self.payloads={"FAKE_A":_bars(140,.07),"FAKE_B":_bars(100,.03)}
    def open(self,request,timeout):
        assert timeout==18
        self.urls.append(request.full_url)
        key=request.full_url.split("/daily/")[1].split("/")[0]
        return Reply(request.full_url,self.payloads[key])


def manifest():
    return {
        "schema_version":VERSION,
        "instruments":[
            {"isin":isin, "symbol":symbol, "venue":"XNAS",
             "instrument_name":"SYNTHETIC TEST ONLY",
             "asset_type":"EQUITY","sector":"Test technology",
             "oil_exposure":"none",
             "reference_urls":[
                 "https://www.sec.gov/Archives/test-not-real",
                 "https://www.nasdaq.com/market-activity/test-not-real",
             ]}
            for isin,symbol in [("US0378331005","FAKE_A"),("US5949181045","FAKE_B")]
        ],
    }


def options(tmp_path,fake):
    src=tmp_path/"reviewed.json"
    src.write_text(json.dumps(manifest()))
    return {
        "manifest_path":src,
        "output":tmp_path/"tiingo_private_batch",
        "repo_root":tmp_path/"repo",
        "api_token":"FAKE_API_TOKEN_NEVER_SEND",
        "personal_rights_ack":True,
        "identity_review_ack":True,
        "opener":fake,
    }


def test_two_symbol_private_batch_and_merged_output(tmp_path):
    fake=Fake();kw=options(tmp_path,fake)
    audit=collect_batch(**kw)
    assert len(fake.urls)==2
    assert audit["individual_source_count"]==2
    assert audit["total_tiingo_requests_this_batch"]==2
    assert audit["trade_ready"] is False and audit["fx_bound"] is False
    assert "FAKE_API_TOKEN_NEVER_SEND" not in json.dumps(audit)
    root=kw["output"]
    combined=json.loads((root/"TIINGO_MULTI_SOURCE_SPEC.json").read_text())
    assert len(combined["assets"])==2
    assert [a["isin"] for a in combined["assets"]]==["US0378331005","US5949181045"]
    assert "fx_source" not in combined
    assert "FAKE_API_TOKEN_NEVER_SEND" not in json.dumps(combined)
    output=tmp_path/"bundle"
    bundle=build_bundle(combined,output)
    assert len(bundle["assets"])==2


@pytest.mark.parametrize("mutation", [
    "no_terms","no_mapping","no_key","duplicate","one",
    "wrong_refs","duplicate_domains","extra_field","unknown_feed",
])
def test_batch_validates_all_instruments_before_first_provider_request(tmp_path,mutation):
    fake=Fake();kw=options(tmp_path,fake)
    src=json.loads(kw["manifest_path"].read_text())
    if mutation=="no_terms":
        kw["personal_rights_ack"]=False
    elif mutation=="no_mapping":
        kw["identity_review_ack"]=False
    elif mutation=="no_key":
        kw["api_token"]=None
    elif mutation=="duplicate":
        src["instruments"][1]["isin"]=src["instruments"][0]["isin"]
    elif mutation=="one":
        src["instruments"].pop()
    elif mutation=="wrong_refs":
        src["instruments"][0]["reference_urls"]=["http://example.com","https://ok.example"]
    elif mutation=="duplicate_domains":
        src["instruments"][0]["reference_urls"]=["https://foo.example/a","https://foo.example/b"]
    elif mutation=="extra_field":
        src["instruments"][0]["EODHD_API_TOKEN"]="FAKE_BAD_INPUT"
    elif mutation=="unknown_feed":
        src["instruments"][0]["asset_type"]="ETN"
    kw["manifest_path"].write_text(json.dumps(src))
    with pytest.raises(ValueError):
        collect_batch(**kw)
    assert fake.urls==[]
    assert not kw["output"].exists()


def test_rerun_cannot_silently_consume_more_personal_quota(tmp_path):
    fake=Fake();kw=options(tmp_path,fake)
    collect_batch(**kw)
    with pytest.raises(ValueError,match="NEW"):
        collect_batch(**kw)
    assert len(fake.urls)==2


def test_live_starter_batch_collection_is_disabled_before_network(tmp_path):
    fake=Fake()
    args=options(tmp_path,fake)
    args["opener"]=None
    with pytest.raises(ValueError,match="TIINGO_STARTER_PERSISTENT_STORAGE_NOT_PERMITTED"):
        collect_batch(**args)
    assert not fake.urls
    assert not args["output"].exists()
