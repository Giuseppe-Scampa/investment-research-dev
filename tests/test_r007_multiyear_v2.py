"""V2 multi-year preregistration and anti-lookahead contracts; synthetic only."""
from datetime import date,timedelta
from pathlib import Path
from decimal import Decimal
import hashlib,json,math
import pytest

from investresearch.validated_multiyear_calendar import session_historical
from investresearch.research_bundle import build_bundle,SYNTHETIC
from investresearch.research_historical_v2 import (
    read_protocol,validate_v2,_anchors,_candidate,_consecutive,
)


def synthetic_bundle(tmp_path,assets_count=5,year=2024):
    d=date(year-1,7,1)
    end=date(year+1,1,3)
    dates=[]
    while d<=end:
        if session_historical(d,"XNYS"):
            dates.append(d)
        d+=timedelta(days=1)
    assets=[]
    for i in range(assets_count):
        p=tmp_path/f"fictional_{i}.csv"
        lines=["date,close,volume"]
        for j,d in enumerate(dates):
            # Opposite trends, deliberately nonpredictive artificial sample
            price=100+i*5+(.012*i-.02)*j+math.sin(j/19+i)
            lines.append(f"{d.isoformat()},{price:.6f},1000000")
        p.write_text("\n".join(lines)+"\n")
        assets.append({"id":f"FAKE_{i}","name":f"NOT_MARKET_DATA_{i}",
                       "isin":"","asset_type":"EQUITY",
                       "currency":"EUR","venue":"XNYS",
                       "sector":"FICTIONAL","oil_exposure":"none",
                       "prices_source":{"provider":"SYNTHETIC_PRICES",
                          "path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}})
    bundle=tmp_path/"bundle"
    build_bundle({"mode":SYNTHETIC,"as_of":f"{year+1}-01-03",
                 "assets":assets},bundle)
    return bundle


def test_v2_keeps_v1_unmodified_and_meets_n_anchors():
    p,sha=read_protocol()
    assert p["parent_v1_sha256"]=="e2ce1ba5928218c2ff78b7962058e7f862713226ff51ef574be5aac8617a26d2"
    assert p["as_of_first"]=="2022-06-01"
    assert p["as_of_last"]=="2026-09-15"
    assert len(_anchors(p,["XNYS"]))>=30
    assert p["negative_control_n"]==1000
    assert len(sha)==64


def test_multi_year_v2_costed_replay_is_not_certified_even_when_positive(tmp_path):
    v=validate_v2(synthetic_bundle(tmp_path))
    assert v["schema_version"]=="HISTORICAL_V2_RESEARCH_NOT_PREDICTIVE_CERTIFICATION"
    assert v["result_type"]=="SYNTHETIC_SOFTWARE_DEMONSTRATION"
    assert v["folds_count"]>=2
    assert v["predictive_edge_certified"] is False
    assert v["trade_ready"] is False
    assert v["null_type1_calibrated"] is False
    assert all(len(f["selected_ids"])==2 and len(f["reversed_bottom_ids"])==2
               for f in v["folds"])
    assert v["top2_random_percentile"] is not None


def test_v2_no_future_target_or_missing_history_independently_scores():
    a={"id":"FAKE","currency":"EUR","venue":"XNYS",
       "asset_type":"EQUITY","sector":"FICTIONAL","oil_exposure":"none"}
    dates=[];d=date(2024,3,1)
    while len(dates)<110:
        if session_historical(d,"XNYS"):
            dates.append((d.isoformat(),Decimal("100")+Decimal(len(dates))/100,Decimal("1000")))
        d+=timedelta(days=1)
    cutoff=dates[61][0]
    base=_candidate(a,dates[:62],cutoff)
    assert base is not None
    assert _candidate(a,dates,cutoff)==base
    assert _consecutive(dates[:61],"XNYS") is True
    assert _candidate(a,dates[:60],dates[59][0]) is None
