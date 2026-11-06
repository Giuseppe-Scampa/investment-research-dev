"""M3/M4: free Tiingo + official ECB contract test with SYNTHETIC FIXTURES ONLY.

Exercises real EXTERNAL pipeline code. NO actual vendor price observations are
present; this is explicitly not an investment result or source entitlement.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from investresearch.market_calendar import session
from investresearch.research_fx_bundle import bind_ecb_fx
from investresearch.research_sources import ECB_CSV_URL
from investresearch.research_bundle import build_bundle, EXTERNAL
from investresearch.research_screen import screen
from investresearch.research_risk import analyze_risk
from investresearch.tactical_research import build_tactical
from investresearch.tax_engine import FiscalRegistry
from investresearch.cli import ROOT

ASOF = date(2026,11,5)


def fixture_paths(tmp_path):
    days = [date(2026,7,1)+timedelta(days=i)
            for i in range((ASOF-date(2026,7,1)).days+1)]
    sessions = [day for day in days if session(day,"XNAS")]
    assert len(sessions)>=61
    price_rows=[]
    for i,d in enumerate(sessions):
        p=100+i*.08
        price_rows.append({
            "date":d.isoformat()+"T00:00:00Z",
            "open":p, "high":p*1.01,"low":p*.99,"close":p,
            "volume":200000,
            "adjOpen":p,"adjHigh":p*1.01,"adjLow":p*.99,
            "adjClose":p, "adjVolume":200000,
            "divCash":0,"splitFactor":1,
        })
    price = tmp_path/"price.json"
    price.write_text(json.dumps(price_rows))
    spec={
        "mode":EXTERNAL,"as_of":ASOF.isoformat(),
        "assets":[{
            "id":"US0378331005","name":"SYNTHETIC TIINGO+ECB TEST DATA",
            "isin":"US0378331005","venue":"XNAS","currency":"USD",
            "asset_type":"EQUITY","sector":"Synthetic test sector",
            "oil_exposure":"none",
            "prices_source":{
                "provider":"TIINGO_EOD_PERSONAL_RESEARCH",
                "source_url":"https://api.tiingo.com/tiingo/daily/FAKE/prices",
                "path":str(price),"sha256":hashlib.sha256(price.read_bytes()).hexdigest(),
                "retrieved_at_utc":"2026-11-05T19:00:00Z",
                "usage_attestation":"PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED",
                "identity_evidence_status":"TWO_SOURCE_ISIN_SYMBOL_VENUE_MANUALLY_REVIEWED",
                "symbol":"FAKE","isin":"US0378331005","venue":"XNAS","currency":"USD",
            },
        }]
    }
    sp=tmp_path/"source-spec.json"
    sp.write_text(json.dumps(spec))
    ecbdays = [d for d in days if d.weekday()<5]
    fx=tmp_path/"ecb.xml"  # label is irrelevant; raw payload is official-format CSV
    fx.write_text("Date,USD\n"+"".join(f"{d},1.10\n" for d in ecbdays))
    meta={
        "provider":"ECB_EUR_FX",
        "source_url":ECB_CSV_URL,
        "path":str(fx),
        "sha256":hashlib.sha256(fx.read_bytes()).hexdigest(),
        "retrieved_at_utc":"2026-11-05T19:10:00Z",
    }
    m=tmp_path/"ecb-meta.json"
    m.write_text(json.dumps(meta))
    return sp,m


def test_free_us_price_plus_official_ecb_real_pipeline_code_synthetic_input(tmp_path):
    price,fxmeta=fixture_paths(tmp_path)
    combined=tmp_path/"tiingo-ecb.spec.json"
    result=bind_ecb_fx(spec_path=price,fx_meta_path=fxmeta,
                       output=combined,repo_root=tmp_path/"repo")
    assert result["usd_assets"]==1
    assert result["fee_or_subscription_required"] is False
    assert result["trade_ready"] is False
    assert result["ecb_dates_available"]>=61
    built=tmp_path/"private-bundle"
    manifest=build_bundle(json.loads(combined.read_text()),built)
    assert "TIINGO_EOD_PERSONAL_RESEARCH" in manifest["source_kinds"]
    assert "ECB_EUR_FX" in manifest["source_kinds"]
    researched=screen(built)
    row=researched["results"][0]
    assert row["market_score"] is not None
    assert row["metrics"]["aligned_observations"]==61
    assert row["trade_ready"] is False
    fiscal=FiscalRegistry.load(ROOT/"config/fiscal/rules_2026.json")
    tactical=build_tactical(researched,fiscal_registry=fiscal)
    risk=analyze_risk(built,researched,tactical)
    assert risk["trade_ready"] is False
    assert risk["dataset_mode"]==EXTERNAL
    assert risk["dataset_manifest_sha256"]==tactical["dataset_manifest_sha256"]


@pytest.mark.parametrize("change,expected",[
    ("meta_hash","SHA-256 mismatch"),
    ("meta_url","official"),
    ("meta_future","after specified as-of"),
    ("meta_timezone","UTC timezone"),
    ("spec_exists","already set"),
    ("no_usd","USD"),
    ("no_fx_rates","stale"),
])
def test_ecb_binding_rejects_false_fx_evidence(tmp_path,change,expected):
    p,m=fixture_paths(tmp_path)
    meta=json.loads(m.read_text())
    spec=json.loads(p.read_text())
    if change=="meta_hash":
        meta["sha256"]="0"*64
    elif change=="meta_url":
        meta["source_url"]="https://untrusted.example.org/ecb.xml"
    elif change=="meta_future":
        meta["retrieved_at_utc"]="2026-11-06T00:00:00Z"
    elif change=="meta_timezone":
        meta["retrieved_at_utc"]="2026-11-05T20:00:00+01:00"
    elif change=="spec_exists":
        spec["fx_source"]={"provider":"FAKE"}
    elif change=="no_usd":
        spec["assets"][0]["currency"]="EUR"
    elif change=="no_fx_rates":
        fxpath=tmp_path/"ecb.xml"
        fxpath.write_text("Date,USD\n2026-08-02,1.08\n")
        meta["sha256"]=hashlib.sha256(fxpath.read_bytes()).hexdigest()
    m.write_text(json.dumps(meta))
    p.write_text(json.dumps(spec))
    dest=tmp_path/"bound.json"
    with pytest.raises(ValueError,match=expected):
        bind_ecb_fx(spec_path=p,fx_meta_path=m,
                    output=dest,repo_root=tmp_path/"repo")
    assert not dest.exists()


def test_ecb_binding_refuses_existing_destination_and_non_private_repository(tmp_path):
    p,m=fixture_paths(tmp_path)
    out=tmp_path/"bound.json"
    out.write_text("{}")
    with pytest.raises(ValueError, match="new private output"):
        bind_ecb_fx(spec_path=p,fx_meta_path=m,output=out,repo_root=tmp_path/"repo")
    project=tmp_path/"repo"
    project.mkdir()
    destination=project/"reports/ECB.json"
    with pytest.raises(ValueError,match="data/private"):
        bind_ecb_fx(spec_path=p,fx_meta_path=m,output=destination,repo_root=project)
