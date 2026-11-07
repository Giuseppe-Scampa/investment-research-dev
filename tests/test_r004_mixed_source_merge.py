"""M3/M4: TEST-ONLY US/EU private data composition; no vendor API calls."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date,timedelta

import pytest

from investresearch.market_calendar import session
from investresearch.research_bundle import EXTERNAL,build_bundle,load_bundle
from investresearch.research_fx_bundle import bind_ecb_fx
from investresearch.research_mixed_source_merge import combine_mixed,VERSION
from investresearch.research_fwb_local import PROVIDER as FWB
from investresearch.research_tiingo_local import PROVIDER as TIINGO,ATTESTATION,MAPPING
from investresearch.research_sources import ECB_CSV_URL
from investresearch.research_screen import screen
from investresearch.research_cli import main
from investresearch.cli import ROOT

AS_OF=date(2026,11,5)
FWB_ISIN="IE00B4L5Y983"
TIINGO_ISIN="US0378331005"


def fixtures(tmp_path):
    fwb_sessions=[]
    tiingo_sessions=[]
    days=[AS_OF-timedelta(days=i) for i in range(180)]
    for d in sorted(days):
        if session(d,"XETR"):
            fwb_sessions.append(d)
        if session(d,"XNAS"):
            tiingo_sessions.append(d)
    fwb_sessions=fwb_sessions[-75:]
    tiingo_sessions=tiingo_sessions[-75:]
    assert len(fwb_sessions)==len(tiingo_sessions)==75

    euro_raw=("Session;Close;Volume\n"+"\n".join(
        f"{d:%d.%m.%Y};{100+n//7},{n%10};200000,0"
        for n,d in enumerate(fwb_sessions))+"\n").encode()
    euro_file=tmp_path/"fictional_FWB_style_original.csv"
    euro_file.write_bytes(euro_raw)
    eu={
        "id":"TEST_EU_INSTRUMENT","isin":FWB_ISIN,
        "name":"FICTIONAL EUROPEAN ETF EOD DATA",
        "asset_type":"ETF_UCITS","venue":"XETR","currency":"EUR",
        "sector":"FICTITIOUS_DIVERSIFIED","oil_exposure":"none",
        "prices_source":{
            "provider":FWB,"path":str(euro_file),
            "sha256":hashlib.sha256(euro_raw).hexdigest(),
            "source_url":"https://live.deutsche-boerse.com/en/etf/fictional/price-history/historical-prices-and-volumes",
            "retrieved_at_utc":"2026-11-05T20:00:00Z",
            "usage_attestation":"FWB_NONCOMMERCIAL_PERSONAL_USE_ACCEPTED",
            "downloaded_market_place":"XETR","download_page_isin":FWB_ISIN,
            "adjustments_claimed":{"splits":True,"dividends":True,"subscription_rights":True},
            "columns":{"date":"Session","close":"Close","volume":"Volume"},
            "delimiter":";","decimal_separator":"comma","date_format":"DMY",
        },
    }

    bars=[]
    for i,d in enumerate(tiingo_sessions):
        close=100+i*.08
        bars.append({
            "date":d.isoformat()+"T00:00:00Z",
            "open":close, "high":close*1.01,"low":close*.99,
            "close":close,"volume":200000,
            "adjOpen":close,"adjHigh":close*1.01,"adjLow":close*.99,
            "adjClose":close,"adjVolume":200000,
            "divCash":0,"splitFactor":1,
        })
    usa_raw=json.dumps(bars).encode()
    usa_file=tmp_path/"fictional_Tiingo_style_original.json"
    usa_file.write_bytes(usa_raw)
    us={
        "id":TIINGO_ISIN,"isin":TIINGO_ISIN,
        "name":"FICTIONAL US NASDAQ EQUITY EOD DATA",
        "asset_type":"EQUITY","venue":"XNAS","currency":"USD",
        "sector":"FICTITIOUS_TECH","oil_exposure":"none",
        "prices_source":{
            "provider":TIINGO,"path":str(usa_file),
            "sha256":hashlib.sha256(usa_raw).hexdigest(),
            "source_url":"https://api.tiingo.com/tiingo/daily/TEST123/prices",
            "retrieved_at_utc":"2026-11-05T20:00:00Z",
            "usage_attestation":ATTESTATION,"identity_evidence_status":MAPPING,
            "symbol":"TEST123","isin":TIINGO_ISIN,
            "venue":"XNAS","currency":"USD",
        },
    }
    eu_spec=tmp_path/"eu_one.json"
    us_spec=tmp_path/"us_one.json"
    for filename,asset in ((eu_spec,eu),(us_spec,us)):
        filename.write_text(json.dumps({"mode":EXTERNAL,"as_of":AS_OF.isoformat(),
                                        "assets":[asset]},sort_keys=True))
    return eu_spec,us_spec,eu,us


def test_combine_original_multimarket_sources_then_bind_ecb_and_build_bundle(tmp_path):
    eu_spec,us_spec,eu,us=fixtures(tmp_path)
    merged=tmp_path/"MIXED_NO_FX.json"
    result=combine_mixed(source_specs=[us_spec,eu_spec],output=merged,repo_root=ROOT)
    assert result["schema_version"]==VERSION
    assert result["source_count"]==2
    assert result["by_provider"]=={FWB:1,TIINGO:1}
    assert result["by_asset_type"]=={"EQUITY":1,"ETF_UCITS":1}
    assert result["fx_needed"] is True
    assert result["source_licences_independently_authenticated"] is False
    assert result["trade_ready"] is False
    source=json.loads(merged.read_text())
    assert len(source["assets"])==2
    assert "fx_source" not in source
    assert source["assets"][0]["isin"]==FWB_ISIN
    # Original-bundle normalizer is independently executed on BOTH providers.
    pre=tmp_path/"BUNDLE_BEFORE_ECB"
    build_bundle(source,pre)
    m,items,fx,events=load_bundle(pre)
    assert len(items)==2 and fx is None and not events
    assert len(items[0][1])==75 and len(items[1][1])==75
    incomplete=screen(pre)
    assert incomplete["ranked_count"]<2
    assert any("MISSING_ECB_FX" in row["warnings"] for row in incomplete["results"])

    original_ecb=("Date,USD\n"+"\n".join(
        f"{(AS_OF-timedelta(days=n)).isoformat()},1.10"
        for n in range(179,-1,-1) if (AS_OF-timedelta(days=n)).weekday()<5)+"\n").encode()
    ecb_file=tmp_path/"FICTIONAL_ECB_SCHEMA_NOT_EXCHANGE_RATES.csv"
    ecb_file.write_bytes(original_ecb)
    meta={
        "provider":"ECB_EUR_FX","source_url":ECB_CSV_URL,
        "path":str(ecb_file),"sha256":hashlib.sha256(original_ecb).hexdigest(),
        "retrieved_at_utc":"2026-11-05T20:00:00+00:00",
    }
    ecb_meta=tmp_path/"FICTIONAL_ECB_META.json"
    ecb_meta.write_text(json.dumps(meta))
    ready=tmp_path/"MIXED_WITH_ECB_FIXTURE.json"
    binding=bind_ecb_fx(spec_path=merged,fx_meta_path=ecb_meta,
                       output=ready,repo_root=ROOT)
    assert binding["assets_total"]==2 and binding["usd_assets"]==1
    book=tmp_path/"MIXED_HASH_BOUND_BUNDLE"
    build_bundle(json.loads(ready.read_text()),book)
    m,items,fx,events=load_bundle(book)
    assert m["mode"]==EXTERNAL
    assert fx and len(fx)>=100
    assert set(m["source_kinds"])=={TIINGO,FWB,"ECB_EUR_FX"}
    assert len(m["assets"])==2
    original=screen(book)
    assert original["universe_size"]==2
    assert all(x["trade_ready"] is False for x in original["results"])
    assert all(x["market_score"] is None or isinstance(x["market_score"],(int,float))
               for x in original["results"])


def test_mixed_cli_emits_same_manifest_and_never_calls_remote(tmp_path):
    eu,us,_,_=fixtures(tmp_path)
    destination=tmp_path/"mixed_cli.json"
    main(["merge-reviewed-sources","--source-spec",str(eu),
          "--source-spec",str(us),"--output",str(destination)])
    assert destination.is_file()
    doc=json.loads(destination.read_text())
    assert len(doc["assets"])==2
    assert "fx_source" not in doc


@pytest.mark.parametrize("mutation,why",[
    ("duplicate_input","Duplicate"),
    ("mismatched_cutoff","identical"),
    ("corrupt_raw_hash","SHA-256"),
    ("missing_usage_rights","noncommercial"),
    ("repeated_isin","Duplicate"),
    ("unknown_provider","only Tiingo"),
    ("future_cutoff","future"),
    ("unsupported_asset_class","asset"),
    ("already_has_fx","exactly one"),
    ("few_sessions","fewer than 61"),
])
def test_mixed_merge_refuses_untrusted_or_inconsistent_sources_without_writing(tmp_path,mutation,why):
    eu_spec,us_spec,eu,us=fixtures(tmp_path)
    if mutation=="duplicate_input":
        inputs=[eu_spec,eu_spec]
    else:
        inputs=[eu_spec,us_spec]
    if mutation=="mismatched_cutoff":
        spec=json.loads(us_spec.read_text());spec["as_of"]="2026-11-04"
        us_spec.write_text(json.dumps(spec))
    elif mutation=="corrupt_raw_hash":
        spec=json.loads(us_spec.read_text())
        spec["assets"][0]["prices_source"]["sha256"]="0"*64
        us_spec.write_text(json.dumps(spec))
    elif mutation=="missing_usage_rights":
        spec=json.loads(eu_spec.read_text())
        spec["assets"][0]["prices_source"]["usage_attestation"]="UNKNOWN"
        eu_spec.write_text(json.dumps(spec))
    elif mutation=="repeated_isin":
        spec=json.loads(us_spec.read_text())
        spec["assets"][0]["isin"]=FWB_ISIN
        us_spec.write_text(json.dumps(spec))
    elif mutation=="unknown_provider":
        spec=json.loads(us_spec.read_text())
        spec["assets"][0]["prices_source"]["provider"]="PAID_VENDOR"
        us_spec.write_text(json.dumps(spec))
    elif mutation=="future_cutoff":
        for p in inputs:
            spec=json.loads(p.read_text());spec["as_of"]="2028-01-01"
            p.write_text(json.dumps(spec))
    elif mutation=="unsupported_asset_class":
        spec=json.loads(us_spec.read_text())
        spec["assets"][0]["asset_type"]="HYPERLEVERAGED_BINARY"
        us_spec.write_text(json.dumps(spec))
    elif mutation=="already_has_fx":
        spec=json.loads(us_spec.read_text());spec["fx_source"]={"provider":"ECB_EUR_FX"}
        us_spec.write_text(json.dumps(spec))
    elif mutation=="few_sessions":
        spec=json.loads(eu_spec.read_text())
        raw=tmp_path/"fictional_FWB_style_original.csv"
        fields=raw.read_bytes().splitlines()
        raw.write_bytes(b"\n".join(fields[:28])+b"\n")
        spec["assets"][0]["prices_source"]["sha256"]=hashlib.sha256(raw.read_bytes()).hexdigest()
        eu_spec.write_text(json.dumps(spec))
    dest=tmp_path/"SHOULD_NOT_EXIST.json"
    with pytest.raises(ValueError,match=why):
        combine_mixed(source_specs=inputs,output=dest,repo_root=ROOT)
    assert not dest.exists()
