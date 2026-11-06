"""R-004: synthetic FWB-style CSV, no source download, no invented licence."""
from __future__ import annotations
import copy
import hashlib
from datetime import date,timedelta
from pathlib import Path

import pytest

from investresearch.research_fwb_local import (
    PROVIDER,PRICE_BASIS,normalize_private_fwb)
from investresearch.research_bundle import build_bundle,EXTERNAL,load_bundle
from investresearch.market_calendar import session


URL=("https://live.deutsche-boerse.com/en/etf/"
     "ishares-core-msci-world-ucits-etf/price-history/historical-prices-and-volumes")
ISIN="IE00B4L5Y983"


def inputs(tmp_path,days=75):
    dates=[]
    d=date(2026,11,6)
    while len(dates)<days:
        if session(d,"XETR"):
            dates.append(d)
        d-=timedelta(days=1)
    dates.reverse()
    raw=("TradingDay;Last;Turnover\n"+"\n".join(
        f"{x:%d.%m.%Y};{100+i//2},{i%10};{1500+i},0"
        for i,x in enumerate(dates))+"\n").encode("utf-8")
    source=tmp_path/"original_exchange_download.csv"
    source.write_bytes(raw)
    meta={
        "provider":PROVIDER,"path":str(source),
        "sha256":hashlib.sha256(raw).hexdigest(),"source_url":URL,
        "retrieved_at_utc":"2026-11-06T20:00:00+00:00",
        "usage_attestation":"FWB_NONCOMMERCIAL_PERSONAL_USE_ACCEPTED",
        "downloaded_market_place":"XETR",
        "download_page_isin":ISIN,
        "adjustments_claimed":{"splits":True,"dividends":True,"subscription_rights":True},
        "columns":{"date":"TradingDay","close":"Last","volume":"Turnover"},
        "delimiter":";","decimal_separator":"comma","date_format":"DMY",
    }
    asset={"id":"SAMPLE_FWB_NO_MARKET_ATTESTATION",
           "isin":ISIN,"name":"Fictional local source test, not a recommendation",
           "venue":"XETR","currency":"EUR","asset_type":"ETF_UCITS",
           "sector":"DIVERSIFIED_ETF_TEST","oil_exposure":"none",
           "index_memberships":[],"prices_source":meta}
    return raw,meta,asset


def test_fwb_original_source_can_pass_through_existing_private_bundle(tmp_path):
    raw,meta,asset=inputs(tmp_path)
    bars,proof=normalize_private_fwb(meta,raw,date(2026,11,6),asset,repo_root=tmp_path)
    assert len(bars)==75
    assert bars[-1]["date"]=="2026-11-06"
    assert proof["price_basis"]==PRICE_BASIS
    assert proof["fwb_data_verified_from_exchange"] is False
    assert proof["historic_dividend_or_split_events_independently_verified"] is False
    spec={"as_of":"2026-11-06","mode":EXTERNAL,"assets":[asset]}
    output=tmp_path/"local-private-research"
    build_bundle(spec,output)
    manifest,items,fx,events=load_bundle(output)
    assert manifest["mode"]==EXTERNAL
    assert items[0][0]["prices"]["price_basis"]==PRICE_BASIS
    assert items[0][0]["prices"]["original_source_sha256"]==meta["sha256"]
    assert len(items[0][1])==75


@pytest.mark.parametrize("field,value,pattern",[
    ("sha256","0"*64,"SHA256|hash"),
    ("usage_attestation","NO","noncommercial"),
    ("download_page_isin","US0378331005","ISIN"),
    ("downloaded_market_place","XFRA","venue"),
    ("source_url","https://evil.example/foo","FWB"),
    ("retrieved_at_utc","2026-11-07T00:00:00+00:00","future"),
    ("columns",{"date":"TradingDay","close":"Price","volume":"Turnover"},"header"),
    ("adjustments_claimed",{"splits":"yes","dividends":True,"subscription_rights":True},"checkbox"),
    ("decimal_separator","auto","separator"),
])
def test_fwb_fails_closed_on_source_or_licence_claim(tmp_path,field,value,pattern):
    raw,meta,asset=inputs(tmp_path)
    meta[field]=value
    with pytest.raises(ValueError,match=pattern):
        normalize_private_fwb(meta,raw,date(2026,11,6),asset,repo_root=tmp_path)


def test_fwb_duplicate_date_malformed_price_and_partial_adjustments(tmp_path):
    raw,meta,asset=inputs(tmp_path,days=30)
    first=raw.splitlines()[1]
    with pytest.raises(ValueError,match="duplicate"):
        normalize_private_fwb(meta,raw+first+b"\n",date(2026,11,6),asset,repo_root=tmp_path)
    with pytest.raises(ValueError,match="malformed"):
        normalize_private_fwb(meta,raw.replace(b"100,0",b"1.000,0",1),
                              date(2026,11,6),asset,repo_root=tmp_path)
    meta["adjustments_claimed"]["dividends"]=False
    _bars,proof=normalize_private_fwb(meta,raw,date(2026,11,6),asset,repo_root=tmp_path)
    assert proof["price_basis"]=="FWB_OPERATOR_SELECTED_PARTIAL_ADJUSTMENTS_NOT_VERIFIED"
