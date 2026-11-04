"""R-004/R-005 Twelve Data Basic one-symbol opt-in diagnostics, NO ranking.

Twelve Data Basic is documented with 8 credits/minute, 800 credits/day and
three market entitlements. This module only performs a single explicitly
authorized US daily time_series request with adjust=splits, not bulk data
ingestion. It never certifies split semantics, ISIN, data rights or tradeability.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

HOST = "https://api.twelvedata.com/time_series"
PROVIDER = "TWELVE_DATA_FREE_SPLITS_REQUESTED_UNVERIFIED"
SCHEMA = "r004-twelve-data-basic-one-symbol-probe-v1"
SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9.]{0,17}$")
VENUE = frozenset({"XNAS", "XNYS"})
CURRENCY = "USD"
MAX_BYTES = 160_000
MAX_BARS = 100
FIELDS = ("date", "close", "volume")


def _json_no_duplicate(pairs):
    out={}
    for key,value in pairs:
        if key in out:
            raise ValueError("Duplicate provider JSON field")
        out[key]=value
    return out


def _bad_constant(value):
    raise ValueError("Non-finite JSON constant")


def _number(val, *, zero_ok=False):
    try:
        n=Decimal(str(val))
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError("Malformed price/volume") from None
    if not n.is_finite() or n < 0 or (n == 0 and not zero_ok):
        raise ValueError("Invalid price/volume")
    return n


def parse_time_series(raw, *, symbol, venue, as_of):
    """Parse a dated, no-future single-symbol provider response (offline pure)."""
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_BYTES:
        raise ValueError("Missing/oversized provider payload")
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid symbol")
    if venue not in VENUE or not isinstance(as_of,date):
        raise ValueError("Invalid venue/as_of")
    try:
        data=json.loads(raw,object_pairs_hook=_json_no_duplicate,
                        parse_constant=_bad_constant)
    except (json.JSONDecodeError,UnicodeDecodeError):
        raise ValueError("Malformed provider JSON") from None
    if not isinstance(data,dict):
        raise ValueError("Provider payload is not a JSON object")
    if data.get("status") == "error" or "code" in data or "message" in data:
        raise ValueError("Provider entitlement/rate limit/error; no paid fallback")
    meta=data.get("meta")
    vals=data.get("values")
    if not isinstance(meta,dict) or not isinstance(vals,list) or not 1<=len(vals)<=MAX_BARS:
        raise ValueError("Invalid Twelve Data daily response envelope")
    if str(meta.get("symbol","")).upper()!=symbol.upper():
        raise ValueError("Provider symbol mismatch")
    if meta.get("interval")!="1day" or meta.get("mic_code")!=venue:
        raise ValueError("Provider venue/interval mismatch")
    if meta.get("currency")!=CURRENCY:
        raise ValueError("Currency mismatch; do not mix local currencies")
    dates=set()
    rows=[]
    for bar in vals:
        if not isinstance(bar,dict):
            raise ValueError("Malformed market bar")
        try:
            d=date.fromisoformat(bar["datetime"])
        except (KeyError,TypeError,ValueError):
            raise ValueError("Invalid market session") from None
        if d > as_of or d.isoformat() in dates:
            raise ValueError("Future/duplicate market session")
        dates.add(d.isoformat())
        if any(field not in bar for field in ("open","high","low","close","volume")):
            raise ValueError("Incomplete OHLCV")
        v={key:_number(bar[key],zero_ok=(key=="volume"))
           for key in ("open","high","low","close","volume")}
        if v["high"] < max(v["open"],v["close"]) or v["low"] > min(v["open"],v["close"]) or v["low"]>v["high"]:
            raise ValueError("Invalid OHLC daily range")
        if v["volume"] != v["volume"].to_integral_value():
            raise ValueError("Noninteger daily volume")
        rows.append({"date":d.isoformat(),"close":str(v["close"]),
                     "volume":str(v["volume"])})
    rows.sort(key=lambda r:r["date"])
    return rows,{"provider_type":str(meta.get("type","UNKNOWN"))[:100],
                 "reported_exchange":str(meta.get("exchange","UNKNOWN"))[:100]}


def _url(symbol, venue, key):
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol) or venue not in VENUE:
        raise ValueError("Invalid single-symbol US pilot selection")
    if not isinstance(key,str) or not key.strip() or len(key)>250:
        raise ValueError("Missing private TWELVE_DATA_API_KEY environment variable")
    return HOST+"?"+urlencode({
        "symbol":symbol.upper(),"mic_code":venue,"interval":"1day",
        "outputsize":str(MAX_BARS),"adjust":"splits",
        "format":"JSON","apikey":key})


def _fetch(url):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            raise ValueError("Redirect prohibited")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    try:
        with opener.open(Request(url,headers={"Accept":"application/json",
                  "User-Agent":"InvestmentResearchPilot/1.0"}),timeout=15) as f:
            data=f.read(MAX_BYTES+1)
    except Exception:
        raise ValueError("Twelve Data source request failed; no retry or paid fallback") from None
    if len(data)>MAX_BYTES:
        raise ValueError("Oversized response")
    return data


def run_pilot(*, symbol, venue, as_of, output, repo_root, api_key,
              live_confirm=False, terms_confirm=False,
              retrieved_at_utc=None, transport=None):
    if live_confirm is not True or terms_confirm is not True:
        raise ValueError("Explicit live and personal-use terms confirmation required")
    now=retrieved_at_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset()!=timedelta(0) or not isinstance(as_of,date) or as_of!=now.date():
        raise ValueError("As-of must be current UTC date (no backdated replay)")
    out=Path(output).resolve()
    root=Path(repo_root).resolve()
    try:
        rel=out.relative_to(root)
    except ValueError:
        rel=None
    if rel is not None and rel.parts[:2]!=("data","private"):
        raise ValueError("Real-source output within repo must be ignored data/private/")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output already exists; no overwrite or implicit repeat")
    url=_url(symbol,venue,api_key)
    raw=_fetch(url) if transport is None else transport(url)
    bars,identity=parse_time_series(raw,symbol=symbol,venue=venue,as_of=as_of)
    h=io.StringIO(newline="")
    w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator="\n")
    w.writeheader();w.writerows(bars)
    csvdata=h.getvalue().encode("utf-8")
    metadata={
        "schema_version":SCHEMA, "provider":PROVIDER,
        "source_endpoint_without_key":HOST,
        "symbol":symbol.upper(),"venue_reported":venue,
        "currency_reported":"USD", **identity,
        "requested_adjust":"splits",
        "actual_adjustment_independently_verified":False,
        "isin":"NOT_RETURNED_NOT_VERIFIED",
        "as_of":as_of.isoformat(),"retrieved_at_utc":now.isoformat(),
        "source_raw_sha256":hashlib.sha256(raw).hexdigest(),
        "normalized_csv_sha256":hashlib.sha256(csvdata).hexdigest(),
        "first_session":bars[0]["date"],"last_session":bars[-1]["date"],
        "session_count":len(bars),
        "terms_acknowledged":"OPERATOR_PERSONAL_NONCOMMERCIAL_INTERNAL",
        "rights_independently_audited":False,
        "research_status":"DIAGNOSTIC_ONLY_NOT_RANKABLE_NOT_TRADE_READY",
        "caveats":[
            "Free plan market entitlement, caching and non-display usage must match account terms",
            "Requested split adjustment is not independently verified from corporate actions",
            "No dividends, complete ISIN mapping, liquidity quality, global coverage or broker bid/ask certified",
            "Do not upload raw market data as a public artifact or automatically feed tactical/global ranking",
        ],
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/"TWELVE_SPLIT_REQUESTED_UNVERIFIED.csv").write_bytes(csvdata)
    (out/"TWELVE_PILOT_METADATA.json").write_text(
        json.dumps(metadata,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    return metadata
