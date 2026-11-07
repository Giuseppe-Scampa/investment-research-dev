"""CI ONLY: create fictional FWB+Tiingo+Euronext Milan+ECB source bytes.

Sources contain purely invented prices, not market data. No network, API
tokens, real issuer data, licensing permission or investment decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date,timedelta
from pathlib import Path

from investresearch.market_calendar import session
from investresearch.research_bundle import EXTERNAL
from investresearch.research_sources import ECB_CSV_URL
from investresearch.research_fwb_local import PROVIDER as FWB
from investresearch.research_euronext_local import PROVIDER as EURONEXT,ATTESTATION as EURONEXT_TERMS
from investresearch.research_tiingo_local import (
    PROVIDER as TIINGO,ATTESTATION,MAPPING,
)

AS_OF=date(2026,11,5)
TIINGO_ISIN="US0378331005"
FWB_ISIN="IE00B4L5Y983"
MIL_ISIN="IT0003128367"


def generate(root):
    dest=Path(root).resolve()
    if dest.exists() or "synthetic_fixture" not in str(dest) or "data/private" not in str(dest):
        raise ValueError("Only a NEW ignored private synthetic_fixture source folder allowed")
    dest.mkdir(parents=True)
    days=sorted(AS_OF-timedelta(days=i) for i in range(180))
    fwb_days=[d for d in days if session(d,"XETR")][-75:]
    us_days=[d for d in days if session(d,"XNAS")][-75:]
    mil_days=[d for d in days if session(d,"XMIL")][-75:]
    assert len(fwb_days)==len(us_days)==len(mil_days)==75
    euro=("Session;Close;Volume\n"+"\n".join(
        f"{d:%d.%m.%Y};{100+i//7},{i%10};200000,0"
        for i,d in enumerate(fwb_days))+"\n").encode()
    euro_path=dest/"SYNTHETIC_FWB_NOT_EXCHANGE_DATA.csv"
    euro_path.write_bytes(euro)
    eu={
        "id":"TEST_ONLY_FWB","isin":FWB_ISIN,
        "name":"NOT_MARKET_DATA_EU_FICTITIOUS_ETF",
        "venue":"XETR","currency":"EUR","asset_type":"ETF_UCITS",
        "sector":"FICTIONAL_EU_DIVERSIFIED","oil_exposure":"none",
        "prices_source":{
            "provider":FWB,"path":str(euro_path),
            "sha256":hashlib.sha256(euro).hexdigest(),
            "source_url":"https://live.deutsche-boerse.com/en/etf/fictional/price-history/historical-prices-and-volumes",
            "retrieved_at_utc":"2026-11-05T20:00:00Z",
            "downloaded_market_place":"XETR",
            "download_page_isin":FWB_ISIN,
            "usage_attestation":"FWB_NONCOMMERCIAL_PERSONAL_USE_ACCEPTED",
            "adjustments_claimed":{"splits":True,"dividends":True,"subscription_rights":True},
            "columns":{"date":"Session","close":"Close","volume":"Volume"},
            "delimiter":";","decimal_separator":"comma","date_format":"DMY",
        },
    }
    bars=[]
    for i,d in enumerate(us_days):
        close=110+i*.085
        bars.append({
            "date":d.isoformat()+"T00:00:00Z",
            "open":close,"high":close*1.01,"low":close*.99,
            "close":close,"volume":250000,
            "adjOpen":close,"adjHigh":close*1.01,"adjLow":close*.99,
            "adjClose":close,"adjVolume":250000,
            "divCash":0,"splitFactor":1,
        })
    usa=json.dumps(bars,separators=(",",":")).encode()
    usa_path=dest/"SYNTHETIC_TIINGO_NOT_PROVIDER_DATA.json"
    usa_path.write_bytes(usa)
    us={
        "id":"TEST_ONLY_US","isin":TIINGO_ISIN,
        "name":"NOT_MARKET_DATA_US_FICTITIOUS_EQUITY",
        "venue":"XNAS","currency":"USD","asset_type":"EQUITY",
        "sector":"FICTIONAL_US_TECH","oil_exposure":"none",
        "prices_source":{
            "provider":TIINGO,"path":str(usa_path),
            "sha256":hashlib.sha256(usa).hexdigest(),
            "source_url":"https://api.tiingo.com/tiingo/daily/CI_FAKE_01/prices",
            "retrieved_at_utc":"2026-11-05T20:00:00Z",
            "usage_attestation":ATTESTATION,"identity_evidence_status":MAPPING,
            "symbol":"CI_FAKE_01","isin":TIINGO_ISIN,
            "venue":"XNAS","currency":"USD",
        },
    }
    milano=("Trading date;Last;Quantity\n"+"\n".join(
        f"{d:%d/%m/%Y};{90+i//8},{i%10};1.000,0"
        for i,d in enumerate(mil_days))+"\n").encode("utf-8-sig")
    milano_file=dest/"SYNTHETIC_EURONEXT_MILAN_NOT_MARKET_DATA.csv"
    milano_file.write_bytes(milano)
    mil={
        "id":"TEST_ONLY_MIL","isin":MIL_ISIN,
        "name":"NOT_MARKET_DATA_MILAN_FICTIONAL_EQUITY",
        "venue":"XMIL","currency":"EUR","asset_type":"EQUITY",
        "sector":"FICTIONAL_EU_TECH","oil_exposure":"none",
        "prices_source":{
            "provider":EURONEXT,"path":str(milano_file),
            "sha256":hashlib.sha256(milano).hexdigest(),
            "source_url":"https://live.euronext.com/en/popout-page/getHistoricalPrice/IT0003128367-MTAA",
            "retrieved_at_utc":"2026-11-05T20:00:00Z",
            "source_market_code":"MTAA","download_page_isin":MIL_ISIN,
            "usage_attestation":EURONEXT_TERMS,
            "data_rights_independently_verified":False,
            "export_adjustment":"ADJUSTED",
            "base_100_export":False,
            "adjustments_claimed":{"splits":True,"dividends":True,"subscription_rights":True},
            "columns":{"date":"Trading date","close":"Last","volume":"Quantity"},
            "delimiter":";","decimal_separator":",","thousands_separator":".",
            "date_format":"DMY_4_SLASH","encoding":"utf-8-sig",
        },
    }
    for label,asset in (("EU",eu),("US",us),("MIL",mil)):
        (dest/f"FICTIONAL_{label}_SOURCE_SPEC.json").write_text(
            json.dumps({"mode":EXTERNAL,"as_of":AS_OF.isoformat(),
                        "assets":[asset]},indent=2)+"\n",encoding="utf-8")
    fx=("Date,USD\n"+"\n".join(
        f"{d.isoformat()},1.14" for d in days if d.weekday()<5)+"\n").encode()
    fx_file=dest/"SYNTHETIC_ECB_SCHEMA_NOT_REAL_FX.csv"
    fx_file.write_bytes(fx)
    meta={
        "provider":"ECB_EUR_FX","source_url":ECB_CSV_URL,
        "path":str(fx_file),"sha256":hashlib.sha256(fx).hexdigest(),
        "retrieved_at_utc":"2026-11-05T20:00:00Z",
    }
    (dest/"FICTIONAL_ECB_META.json").write_text(json.dumps(meta,indent=2)+"\n")
    (dest/"THIS_IS_NOT_REAL_MARKET_DATA.txt").write_text(
        "FICTITIOUS TEST ONLY: prices, FX and source URL fields are invented. "
        "Original-schema parser and private integration test, not real source attestation.\n")
    return dest


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    generate(a.output)
    print("SYNTHETIC_MIXED_SOURCE_FIXTURE_CREATED; REAL MARKET QUOTES=ZERO")


if __name__=="__main__":
    main()
