"""Read-only *real* market-data acquisition test, no raw-data publication.

Deutsche Börse Xetra PDS, registry.opendata.aws/deutsche-boerse-pds.
Historical minute bar source, NONCOMMERCIAL license, DEPRECATED/UNMAINTAINED.
Never equate minute EndPrice to official adjusted daily closing/total return.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener,HTTPRedirectHandler

HOST="https://s3.eu-central-1.amazonaws.com/deutsche-boerse-xetra-pds/"
SAMPLES=(
    "2019-04-18/2019-04-18_BINS_XETR14.csv",
    "2018-02-01/2018-02-01_BINS_XETR14.csv",
)
COLUMNS={"ISIN","Date","Time","StartPrice","MaxPrice",
         "MinPrice","EndPrice","TradedVolume","Currency"}
MAX_BYTES=9_000_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def strict_probe(payload: bytes,expected_day:str) -> dict:
    if not isinstance(payload,bytes) or not 0<len(payload)<=MAX_BYTES:
        raise ValueError("PDS original minute source missing/oversized")
    if b"\0" in payload:
        raise ValueError("PDS original source is not plain CSV")
    raw=payload.decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames):
        raise ValueError("Original Xetra PDS minute CSV columns mismatch")
    rows=0
    isins=set()
    for rec in reader:
        if rows>=100_000:
            raise ValueError("PDS minute file exceeds bounded sampling cap")
        if rec.get("Date")!=expected_day:
            raise ValueError("Xetra PDS source date mismatch")
        isin=rec.get("ISIN","")
        if not isinstance(isin,str) or len(isin)!=12 or not isin.isalnum():
            raise ValueError("Xetra PDS missing/invalid ISIN form")
        isins.add(isin)
        vals=[Decimal(rec[name]) for name in
              ("StartPrice","MaxPrice","MinPrice","EndPrice","TradedVolume")]
        if (any(not x.is_finite() or x<0 for x in vals)
                or min(vals[:4])<=0
                or vals[1]<max(vals[0],vals[3]) or vals[2]>min(vals[0],vals[3])):
            raise ValueError("Xetra PDS OHLC minute values inconsistent")
        rows+=1
    if rows<2 or not isins:
        raise ValueError("Xetra PDS original minute source lacks enough observations")
    return {
        "source":"DEUTSCHE_BOERSE_XETRA_PDS_DEPRECATED_NONCOMMERCIAL",
        "observation_date":expected_day,
        "minute_observation_count":rows,
        "distinct_isin_count":len(isins),
        "original_csv_sha256":hashlib.sha256(payload).hexdigest(),
        "real_source_retrieved":True,
        "is_adjusted_daily_close":False,
        "point_in_time_membership_verified":False,
        "corporate_actions_verified":False,
        "backtest_ready":False,
        "permission":"NONCOMMERCIAL_RESEARCH_ONLY_NOT_REDISTRIBUTABLE_OR_AUTOMATICALLY_TRADE_READY",
    }


def main():
    http=build_opener(NoRedirect())
    for path in SAMPLES:
        url=HOST+path
        req=Request(url,headers={"User-Agent":"investment-research-2026-readonly-validation/1.0","Accept":"text/csv"})
        try:
            with http.open(req,timeout=12) as response:
                data=response.read(MAX_BYTES+1)
        except (URLError,HTTPError,TimeoutError,OSError) as exc:
            # Never infer payload validity from an unavailable network source.
            print("XETRA_PDS_SOURCE_UNAVAILABLE",path,type(exc).__name__)
            continue
        try:
            out=strict_probe(data,path[:10])
        except (ValueError,ArithmeticError,UnicodeError) as exc:
            # Source acquired but failed validation: do not quietly fall back.
            print("XETRA_PDS_VALIDATION_FAILED",type(exc).__name__)
            raise SystemExit(2) from None
        print("XETRA_PDS_REAL_ORIGINAL_SOURCE_VERIFIED_AGGREGATES_ONLY")
        print(json.dumps(out,sort_keys=True))
        return
    print("XETRA_PDS_SOURCE_UNAVAILABLE_NO_REAL_DATA_CLAIM")


if __name__=="__main__":
    main()
