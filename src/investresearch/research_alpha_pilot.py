"""R-004/R-005: strictly opt-in Alpha Vantage free-tier DAILY acquisition pilot.

The free TIME_SERIES_DAILY/compact endpoint provides at most the recent 100
unadjusted bars. It does NOT establish a split-adjusted total return series,
ISIN, trading venue, corporate actions, market-data rights or broker quote.
Outputs are LOCAL ONLY and never used to rank instruments automatically.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

ENDPOINT = "https://www.alphavantage.co/query"
PROVIDER = "ALPHAVANTAGE_DAILY_RAW_UNVERIFIED"
SCHEMA = "r004-alphavantage-free-daily-pilot-v1"
MAX_RESPONSE_BYTES = 200_000
SYMBOL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\\-]{0,19}$")
VENUES = frozenset({"XNYS", "XNAS", "XMIL", "XETR", "XPAR"})
PRICE_KEYS = {
    "1. open": "Open", "2. high": "High", "3. low": "Low",
    "4. close": "Close", "5. volume": "Volume",
}
CSV_FIELDS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def _unique_object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field in market-data payload")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite value in market-data payload")


def _number(value, *, zero_ok=False):
    try:
        n = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Malformed market-data number") from None
    if not n.is_finite() or n < 0 or (n == 0 and not zero_ok):
        raise ValueError("Invalid non-positive or non-finite market-data number")
    return n


def parse_daily(payload, symbol, as_of):
    """Pure parser of official documented API JSON, not source authentication."""
    if not isinstance(payload, bytes) or not payload or len(payload)>MAX_RESPONSE_BYTES:
        raise ValueError("Invalid market-data payload size")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid explicit symbol")
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    try:
        data=json.loads(payload, object_pairs_hook=_unique_object_pairs,
                        parse_constant=_invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Malformed market-data JSON") from None
    if not isinstance(data, dict):
        raise ValueError("Unexpected market-data response")
    if any(k in data for k in ("Note", "Information", "Error Message")):
        raise ValueError("Provider returned rate-limit, entitlement or error; no fallback")
    meta = data.get("Meta Data")
    bars = data.get("Time Series (Daily)")
    if not isinstance(meta, dict) or not isinstance(bars, dict) or not bars:
        raise ValueError("Provider response lacks the documented daily series")
    if str(meta.get("2. Symbol", "")).upper() != symbol.upper():
        raise ValueError("Response symbol does not match explicit request")
    if len(bars)>100:
        raise ValueError("Unexpected more than 100 compact daily records")
    latest = meta.get("3. Last Refreshed")
    if latest:
        if not isinstance(latest,str) or len(latest)<10:
            raise ValueError("Invalid provider refresh date")
        try:
            refreshed = date.fromisoformat(latest[:10])
        except ValueError:
            raise ValueError("Invalid provider refresh date") from None
        if refreshed > as_of:
            raise ValueError("Provider claims a future refresh date")
    output=[]
    for key, raw in bars.items():
        if not isinstance(key, str):
            raise ValueError("Invalid daily session date")
        try:
            session = date.fromisoformat(key)
        except ValueError:
            raise ValueError("Invalid daily session date") from None
        if session>as_of:
            raise ValueError("Future market session in provider response")
        if not isinstance(raw, dict) or set(raw)!=set(PRICE_KEYS):
            raise ValueError("Daily OHLCV fields malformed or missing")
        vals={out:_number(raw[src],zero_ok=out=="Volume")
              for src,out in PRICE_KEYS.items()}
        if vals["High"] < max(vals["Open"], vals["Close"], vals["Low"]):
            raise ValueError("OHLC high inconsistent")
        if vals["Low"] > min(vals["Open"], vals["Close"]):
            raise ValueError("OHLC low inconsistent")
        if vals["Volume"] != vals["Volume"].to_integral_value():
            raise ValueError("Daily market volume not an integer")
        output.append({"Date":session.isoformat(),
                       **{v:str(vals[v]) for v in PRICE_KEYS.values()}})
    output.sort(key=lambda x:x["Date"])
    if not output:
        raise ValueError("No usable daily records")
    return output


def _url(symbol, api_key):
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid explicit symbol")
    if not isinstance(api_key,str) or not api_key.strip() or len(api_key)>250:
        raise ValueError("Alpha Vantage key must be supplied through environment")
    # Query parameters are fixed; never accept arbitrary host or function.
    return ENDPOINT+"?"+urllib.parse.urlencode({
        "function":"TIME_SERIES_DAILY", "symbol":symbol.upper(),
        "outputsize":"compact", "datatype":"json", "apikey":api_key})


def _fetch_once(url):
    """One HTTPS request, no proxy/redirects; errors never reveal the API key."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("Market data redirect is disallowed")
    request=urllib.request.Request(url,headers={
        "Accept":"application/json", "User-Agent":"InvestmentResearchPilot/1.0"})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            raw=response.read(MAX_RESPONSE_BYTES+1)
    except Exception:
        raise ValueError("Alpha Vantage request failed: no retries/fallback; check local limits") from None
    if len(raw)>MAX_RESPONSE_BYTES:
        raise ValueError("Alpha Vantage response exceeds size cap")
    return raw


def run_pilot(*, symbol, venue, as_of, output, repo_root, api_key,
              live_confirm=False, terms_confirm=False,
              retrieved_at_utc=None, transport=None):
    if live_confirm is not True or terms_confirm is not True:
        raise ValueError("Explicit live and source-terms confirmation required")
    if venue not in VENUES:
        raise ValueError("Market MIC must be explicitly selected; not inferred from ticker")
    if not isinstance(as_of,date):
        raise ValueError("as_of must be a date")
    now = retrieved_at_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset()!=timedelta(0):
        raise ValueError("UTC-aware collection time required")
    if as_of!=now.date():
        raise ValueError("Pilot can only be run for today's UTC as_of, not historical replay")
    out=Path(output).resolve()
    root=Path(repo_root).resolve()
    try:
        relative=out.relative_to(root)
    except ValueError:
        relative=None
    if relative is not None and relative.parts[:2]!=("data","private"):
        raise ValueError("Market-data pilot output inside repo must be ignored data/private/")
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output already exists; refuse overwrite/accidental repeated pilot")
    url=_url(symbol,api_key)
    payload=(_fetch_once(url) if transport is None else transport(url))
    bars=parse_daily(payload,symbol,as_of)
    h=io.StringIO(newline="")
    w=csv.DictWriter(h,fieldnames=CSV_FIELDS,lineterminator="\n")
    w.writeheader();w.writerows(bars)
    csv_data=h.getvalue().encode("utf-8")
    metadata={
        "schema_version":SCHEMA, "provider":PROVIDER,
        "source_endpoint_no_key":ENDPOINT,
        "function":"TIME_SERIES_DAILY", "outputsize":"compact",
        "symbol":symbol.upper(), "venue_asserted_not_verified":venue,
        "isin":"UNVERIFIED_NOT_RETURNED_BY_PROVIDER",
        "as_of":as_of.isoformat(),
        "retrieved_at_utc":now.isoformat(),
        "raw_payload_sha256":hashlib.sha256(payload).hexdigest(),
        "normalized_csv_sha256":hashlib.sha256(csv_data).hexdigest(),
        "session_count":len(bars), "oldest_session":bars[0]["Date"],
        "latest_session":bars[-1]["Date"],
        "source_terms_status":"USER_ACKNOWLEDGED_NOT_INDEPENDENTLY_AUDITED",
        "usage":"LOCAL_DIAGNOSTIC_ONLY_NO_PUBLIC_REDISTRIBUTION",
        "price_basis":"RAW_DAILY_CLOSE_NOT_ADJUSTED_OR_TOTAL_RETURN",
        "corporate_actions":"NOT_VERIFIED",
        "license":"NOT_VERIFIED_FOR_AUTOMATED_RANKING_OR_DISTRIBUTION",
        "research_status":"NOT_TRADE_READY_NOT_ELIGIBLE_FOR_GLOBAL_FUNNEL",
        "warnings":[
            "Ticker is not an ISIN; venue is operator-asserted and may be incorrect",
            "Free compact records cover at most 100 recent sessions, not corporate actions",
            "Daily close is not a real execution bid/ask, nor total-return data",
            "Public redistribution or mass non-display use rights are not established",
            "This isolated pilot does not write to any screening/ranking bundle",
        ],
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/"ALPHA_DAILY_UNVERIFIED.csv").write_bytes(csv_data)
    (out/"ALPHA_PILOT_METADATA.json").write_text(
        json.dumps(metadata,sort_keys=True,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    return metadata
