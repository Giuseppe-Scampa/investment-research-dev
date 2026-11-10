"""Read-only third-party real S&P500 historical CSV probe (NOT primary exchange).

Source: https://dataset.aethereal.top/datasets/sp500-stock-prices
Terms stated by publisher: Free for research and education.
CRITICAL: contains only *current* constituents, built retrospectively;
survivorship bias, upstream adjusted-price lineage not authenticated.
Do not publish prices or treat this as a verified ISIN-based investment
candidate universe.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

URL="https://dataset.aethereal.top/files/sp500-stock-prices.csv"
HEADERS=("date","ticker","open","high","low","close","adj_close","volume")
MAX_BYTES=110_000_000
MAX_ROWS=2_000_000


def quality_check(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:
        raise ValueError("Real research CSV original bytes absent or too large")
    h=hashlib.sha256(raw).hexdigest()
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames is None or tuple(reader.fieldnames)!=HEADERS:
        raise ValueError("Research market dataset original CSV headers mismatch")
    n=0;tickers=set();min_day="9999-99-99";max_day="0000-00-00"
    adjusted_differences=0
    invalid=0
    for row in reader:
        n+=1
        if n>MAX_ROWS:raise ValueError("Research dataset exceeds bounded original row count")
        if None in row or any(v is None for v in row.values()):
            invalid+=1;continue
        d=row["date"];symbol=row["ticker"]
        if not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}",d):
            invalid+=1;continue
        if not re.fullmatch(r"[A-Z0-9.\\-]{1,15}",symbol):
            invalid+=1;continue
        try:
            close=float(row["close"]);adj=float(row["adj_close"])
            vol=float(row["volume"])
        except (TypeError,ValueError):
            invalid+=1;continue
        if not all(math.isfinite(x) for x in (close,adj,vol)) or min(close,adj)<=0 or vol<0:
            invalid+=1;continue
        tickers.add(symbol)
        min_day=min(min_day,d);max_day=max(max_day,d)
        if abs(close-adj)>max(1e-5,abs(close)*1e-6):
            adjusted_differences+=1
    if n<20000 or len(tickers)<50 or invalid>n*.01:
        raise ValueError("Research market dataset failed basic completeness thresholds")
    return {
       "schema_version":"THIRD_PARTY_REAL_RESEARCH_HISTORY_PROBE_V1",
       "publisher":"AETHEREAL_FREE_RESEARCH_EDUCATION",
       "original_source_url":URL,
       "original_bytes_sha256":h,
       "original_total_rows":n,
       "valid_distinct_source_tickers":len(tickers),
       "invalid_or_incomplete_rows":invalid,
       "min_date":min_day,"max_date":max_day,
       "close_different_from_adj_close_rows":adjusted_differences,
       "acquisition":"ORIGINAL_BYTES_FETCHED_AND_SCHEMA_CHECKED",
       "source_exchange_primary":False,
       "corporate_actions_verified":False,
       "historical_universe_survivorship_bias":"CURRENT_SP500_MEMBERS_ONLY",
       "point_in_time_membership_verified":False,
       "isin_currency_venue_verified":False,
       "income_tax_treatment_verified":False,
       "predictive_edge_certified":False,
       "trade_ready":False,
    }


def main():
    try:
        req=Request(URL,headers={
            "User-Agent":"investment-research-2026-noncommercial-research/1.0",
            "Accept":"text/csv"})
        with urlopen(req,timeout=45) as f:
            raw=f.read(MAX_BYTES+1)
    except (HTTPError,URLError,OSError,TimeoutError) as exc:
        print("SP500_RESEARCH_DATA_SOURCE_UNAVAILABLE",type(exc).__name__)
        return
    try:
        report=quality_check(raw)
    except (ValueError,UnicodeError) as exc:
        print("SP500_RESEARCH_DATA_VALIDATION_FAILED",type(exc).__name__)
        raise SystemExit(2) from None
    print("REAL_THIRD_PARTY_HISTORY_ACQUIRED_BUT_NOT_INVESTMENT_VALIDATED")
    print(json.dumps(report,sort_keys=True))
    # Raw CSV intentionally retained ONLY in memory, never in GitHub
    # artifacts, public git, logs or persistent CI storage.


if __name__=="__main__":
    main()
