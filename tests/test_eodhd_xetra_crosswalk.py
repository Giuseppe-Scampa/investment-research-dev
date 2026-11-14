"""Independent-source Xetra ↔ EODHD identity join; fixtures are entirely invented."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date

import pytest

from investresearch.research_eodhd_xetra_crosswalk import (
    PROVIDER, parse_eodhd_xetra_catalog, join_xetra_eodhd, write_crosswalk,
)
from investresearch.research_xetra_universe import parse_xetra, PROVIDER as XPROVIDER


ASOF = date(2026, 11, 5)
XETRA_URL = ("https://www.cashmarket.deutsche-boerse.com/resource/blob/"
             "1528/0447d5f72a1ca9cd3f00a6bd5f8805cc/data/"
             "t7-xetr-allTradableInstruments.csv")


def xetra():
    keys = ["Product Status","Instrument Status","Instrument","ISIN",
            "Mnemonic","MIC Code","Settlement Currency","Instrument Type"]
    entries = [
        ("US0378331005","AAP","CS"),
        ("IE00B4L5Y983","WORLD","ETF"),
        ("JE00B1VS3333","SILV","ETC"),
        ("CH1135202120","NAMEX","ETN"),
    ]
    b = io.StringIO(newline="")
    writer = csv.writer(b,delimiter=";",lineterminator="\n")
    writer.writerow(keys)
    for isin, sym, typ in entries:
        writer.writerow(["Active","Active","Synthetic",isin,sym,"XETR","EUR",typ])
    payload=("Market:;XETR\nDate Last Update:;04.11.2026\n"+b.getvalue()).encode()
    meta={"provider":XPROVIDER,"source_url":XETRA_URL,
          "sha256":hashlib.sha256(payload).hexdigest(),
          "retrieved_at_utc":"2026-11-05T16:00:00Z"}
    return payload,meta


def vendor():
    rows=[
        {"Code":"AA","Name":"Synthetic","Country":"DE","Exchange":"XETRA",
         "Currency":"EUR","Type":"Common Stock","Isin":"US0378331005"},
        {"Code":"WW","Name":"Synthetic","Country":"IE","Exchange":"XETRA",
         "Currency":"EUR","Type":"ETF","Isin":"IE00B4L5Y983"},
        {"Code":"SS","Name":"Synthetic","Country":"JE","Exchange":"XETRA",
         "Currency":"EUR","Type":"ETF","Isin":"JE00B1VS3333"},
        {"Code":"TT","Name":"Synthetic","Country":"CH","Exchange":"XETRA",
         "Currency":"EUR","Type":"ETN","Isin":"CH1135202120"},
        {"Code":"NO","Name":"Synthetic","Country":"IE","Exchange":"XETRA",
         "Currency":"EUR","Type":"ETF","Isin":None},
    ]
    payload=json.dumps(rows).encode()
    meta={"provider":PROVIDER,
          "source_url":"https://eodhd.com/api/exchange-symbol-list/XETRA",
          "sha256":hashlib.sha256(payload).hexdigest(),
          "retrieved_at_utc":"2026-11-05T16:00:00Z",
          "usage_attestation":"PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED"}
    return payload,meta


def test_two_source_crosswalk_preserves_type_disagreement_and_excludes_missing_isin(tmp_path):
    raw,meta=xetra()
    x_rows,x_meta=parse_xetra(raw,meta,as_of=ASOF)
    market,rights=vendor()
    v_rows,v_meta=parse_eodhd_xetra_catalog(market,rights,as_of=ASOF)
    out,audit=join_xetra_eodhd(x_rows,x_meta,v_rows,v_meta)
    assert audit["xetra_active_reference_count"]==4
    assert audit["matched_count"]==3
    assert audit["rejection_counts"]["ASSET_CLASS_DISAGREEMENT_NEEDS_REVIEW"]==1
    assert v_meta["skipped_vendor"]["ISIN_MISSING_OR_INVALID"]==1
    assert all(r["research_status"].endswith("NOT_TRADE_READY") for r in out)
    assert not audit["trade_ready"]
    assert all("price" not in r for r in out)
    assert any(r["eodhd_symbol"]=="AA.XETRA" for r in out)
    xsrc=tmp_path/"xetra.csv";xsrc.write_bytes(raw)
    xm=tmp_path/"x_meta.json";xm.write_text(json.dumps(meta))
    vsrc=tmp_path/"vendor.json";vsrc.write_bytes(market)
    vm=tmp_path/"v_meta.json";vm.write_text(json.dumps(rights))
    result=write_crosswalk(xsrc,xm,vsrc,vm,ASOF,tmp_path/"output",repo_root=tmp_path/"repo")
    assert result["matched_count"]==3
    assert (tmp_path/"output/XETRA_EODHD_IDENTITY_COVERAGE.csv").exists()
    with pytest.raises(ValueError,match="overwrite"):
        write_crosswalk(xsrc,xm,vsrc,vm,ASOF,tmp_path/"output",repo_root=tmp_path/"repo")


@pytest.mark.parametrize("change,expected",[
    ("rights","acknowledgement"),
    ("sha","SHA256"),
    ("url","official"),
    ("time","as-of"),
    ("duplicate","Duplicated"),
    ("schema","schema"),
])
def test_vendor_catalog_validation_blocks_bad_rights_identity_and_schema(change,expected):
    raw,meta=vendor()
    rows=json.loads(raw)
    if change=="rights":meta["usage_attestation"]="unknown"
    if change=="sha":meta["sha256"]="0"*64
    if change=="url":meta["source_url"]="https://evil.invalid/api/exchange-symbol-list/XETRA"
    if change=="time":meta["retrieved_at_utc"]="2026-11-06T12:00:00Z"
    if change=="duplicate":
        rows.append(dict(rows[0]))
        raw=json.dumps(rows).encode()
        meta["sha256"]=hashlib.sha256(raw).hexdigest()
    if change=="schema":
        del rows[0]["Isin"]
        raw=json.dumps(rows).encode()
        meta["sha256"]=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError,match=expected):
        parse_eodhd_xetra_catalog(raw,meta,as_of=ASOF)


def test_provider_conflicting_duplicate_isin_is_review_not_auto_join():
    raw,meta=xetra()
    x,xman=parse_xetra(raw,meta,as_of=ASOF)
    raw,vmeta=vendor()
    v,vman=parse_eodhd_xetra_catalog(raw,vmeta,as_of=ASOF)
    v.append({**v[0],"symbol":"OTHER.XETRA"})
    matches,audit=join_xetra_eodhd(x,xman,v,vman)
    assert audit["matched_count"]==2
    assert audit["rejection_counts"]["DUPLICATE_ISIN_VENDOR_LISTINGS_NEED_REVIEW"]==1
