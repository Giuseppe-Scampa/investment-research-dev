"""Original-schema Euronext Milan/Paris CSV intake, entirely fictional history."""
from __future__ import annotations

import copy
import hashlib
from datetime import date, timedelta

import pytest

from investresearch.market_calendar import session
from investresearch.research_bundle import EXTERNAL,build_bundle,load_bundle
from investresearch.research_screen import screen
from investresearch.research_euronext_local import (
    ATTESTATION, PROVIDER,PRICE_BASIS_ADJUSTED,PRICE_BASIS_UNADJUSTED,
    normalize_private_euronext,
)

ASOF=date(2026,11,6)


def inputs(tmp_path,*,market="MTAA",days=75):
    venue="XMIL" if market!="XPAR" else "XPAR"
    isin="IT0003128367" if venue=="XMIL" else "FR0000121014"
    dates=[]
    d=ASOF
    while len(dates)<days:
        if session(d,venue):
            dates.append(d)
        d-=timedelta(days=1)
    dates.reverse()
    raw=("Trading date;Last;Quantity\n"+"\n".join(
        f"{d:%d/%m/%Y};{100+i//7},{i%10};1.000,0"
        for i,d in enumerate(dates))+"\n").encode("utf-8-sig")
    path=tmp_path/f"FICTIONAL_{market}_EURONEXT_EXPORT.csv"
    path.write_bytes(raw)
    meta={
        "provider":PROVIDER,
        "path":str(path),
        "sha256":hashlib.sha256(raw).hexdigest(),
        "source_url":f"https://live.euronext.com/en/popout-page/getHistoricalPrice/{isin}-{market}",
        "retrieved_at_utc":"2026-11-06T20:00:00Z",
        "source_market_code":market,
        "download_page_isin":isin,
        "usage_attestation":ATTESTATION,
        "data_rights_independently_verified":False,
        "export_adjustment":"ADJUSTED",
        "base_100_export":False,
        "adjustments_claimed":{
            "splits":True,"dividends":True,"subscription_rights":True,
        },
        "columns":{"date":"Trading date","close":"Last","volume":"Quantity"},
        "delimiter":";","decimal_separator":",","thousands_separator":".",
        "date_format":"DMY_4_SLASH","encoding":"utf-8-sig",
    }
    asset={
        "id":f"TEST_ONLY_{market}",
        "isin":isin,"name":f"NOT_MARKET_DATA_{market}_FICTIONAL",
        "asset_type":"EQUITY","venue":venue,"currency":"EUR",
        "sector":"FICTIONAL_NONOIL",
        "oil_exposure":"none",
        "prices_source":meta,
    }
    return raw,meta,asset


@pytest.mark.parametrize("market",["MTAA","XPAR"])
def test_euronext_original_schema_to_bundle_and_screen_preserves_source(market,tmp_path):
    raw,meta,asset=inputs(tmp_path,market=market)
    bars,proof=normalize_private_euronext(meta,raw,ASOF,asset,repo_root=tmp_path)
    assert len(bars)==75
    assert bars[-1]["date"]==ASOF.isoformat()
    assert bars[-1]["volume"]=="1000.0"
    assert proof["price_basis"]==PRICE_BASIS_ADJUSTED
    assert proof["euronext_data_rights_independently_verified"] is False
    folder=tmp_path/"SOURCE_BOUND_EURONEXT_BUNDLE"
    build_bundle({"mode":EXTERNAL,"as_of":ASOF.isoformat(),"assets":[asset]},folder)
    manifest,assets,fx,_=load_bundle(folder)
    assert len(assets)==1 and fx is None
    assert assets[0][0]["prices"]["provider"]==PROVIDER
    assert assets[0][0]["prices"]["euronext_original_source_sha256"]==meta["sha256"]
    result=screen(folder)
    assert result["universe_size"]==1
    row=result["results"][0]
    assert "EURONEXT_PRICE_ADJUSTMENTS_NOT_INDEPENDENTLY_VERIFIED" in row["warnings"]
    assert row["trade_ready"] is False


def test_euronext_non_adjusted_and_partial_adjustments_cannot_be_ranked(tmp_path):
    raw,meta,asset=inputs(tmp_path)
    for variant in ("NON_ADJUSTED","PARTIAL"):
        changed=copy.deepcopy(meta)
        if variant=="NON_ADJUSTED":
            changed["export_adjustment"]="NON_ADJUSTED"
        else:
            changed["adjustments_claimed"]["dividends"]=False
        adjusted=copy.deepcopy(asset);adjusted["prices_source"]=changed
        original,notes=normalize_private_euronext(changed,raw,ASOF,adjusted,repo_root=tmp_path)
        assert notes["price_basis"]==PRICE_BASIS_UNADJUSTED
        bundle=tmp_path/f"BUNDLE_{variant}"
        build_bundle({"mode":EXTERNAL,"as_of":ASOF.isoformat(),"assets":[adjusted]},bundle)
        row=screen(bundle)["results"][0]
        assert row["market_score"] is None
        assert "EURONEXT_UNADJUSTED_OR_PARTIAL_NO_RANK" in row["warnings"]
        assert row["trade_ready"] is False


@pytest.mark.parametrize("bad,reason",[
    ("bad_hash","SHA-256"),
    ("bad_isin","ISIN"),
    ("bad_market","segment"),
    ("wrong_url","page mismatch"),
    ("missing_rights","noncommercial"),
    ("fake_verified_rights","cannot be certified"),
    ("base100","Base-100"),
    ("date_after_retrieval","follows original"),
    ("bad_locale","locale"),
    ("broken_price","numeric|Malformed"),
    ("duplicate_date","Duplicate"),
    ("missing_close_header","headers"),
    ("missing_adjustment_choice","selection"),
    ("bad_adjustment_flag","boolean"),
    ("unsupported_currency","EUR"),
])
def test_euronext_rejects_unverified_csv_or_identity_before_rank(tmp_path,bad,reason):
    raw,meta,asset=inputs(tmp_path)
    meta=copy.deepcopy(meta);asset=copy.deepcopy(asset)
    if bad=="bad_hash":meta["sha256"]="0"*64
    elif bad=="bad_isin":meta["download_page_isin"]="FR0000121014"
    elif bad=="bad_market":meta["source_market_code"]="XAMS"
    elif bad=="wrong_url":meta["source_url"]=meta["source_url"].replace("MTAA","XPAR")
    elif bad=="missing_rights":meta["usage_attestation"]="NOT_APPROVED"
    elif bad=="fake_verified_rights":meta["data_rights_independently_verified"]=True
    elif bad=="base100":meta["base_100_export"]=True
    elif bad=="date_after_retrieval":meta["retrieved_at_utc"]="2026-11-05T00:00:00Z"
    elif bad=="bad_locale":meta["decimal_separator"]="?"
    elif bad=="missing_close_header":meta["columns"]["close"]="Settle"
    elif bad=="missing_adjustment_choice":meta["export_adjustment"]="UNKNOWN"
    elif bad=="bad_adjustment_flag":meta["adjustments_claimed"]["splits"]="True"
    elif bad=="unsupported_currency":asset["currency"]="USD"
    elif bad=="broken_price":
        raw=raw.replace(b"100,0",b"1,000,0",1)
        meta["sha256"]=hashlib.sha256(raw).hexdigest()
    elif bad=="duplicate_date":
        raw+=raw.splitlines()[-1]+b"\n"
        meta["sha256"]=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError,match=reason):
        normalize_private_euronext(meta,raw,ASOF,asset,repo_root=tmp_path)


def test_euronext_certificate_without_payoff_is_not_ranked_even_adjusted(tmp_path):
    raw,meta,asset=inputs(tmp_path)
    meta["source_market_code"]="ETLX"
    meta["source_url"]=meta["source_url"].replace("MTAA","ETLX")
    asset["asset_type"]="CERTIFICATE"
    with pytest.raises(ValueError,match="unit"):
        normalize_private_euronext(meta,raw,ASOF,asset,repo_root=tmp_path)
    meta["close_unit_operator_asserted"]="EUR_PER_CERTIFICATE_UNIT"
    bundle=tmp_path/"CERTIFICATE_BUNDLE"
    build_bundle({"mode":EXTERNAL,"as_of":ASOF.isoformat(),"assets":[asset]},bundle)
    row=screen(bundle)["results"][0]
    assert row["market_score"] is None
    assert "EURONEXT_CERTIFICATE_PAYOFF_AND_UNITS_NOT_MODELED_NO_RANK" in row["warnings"]
