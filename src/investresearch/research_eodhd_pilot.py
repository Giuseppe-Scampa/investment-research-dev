"""R-004/R-005: EODHD evaluation-only EOD + split/dividend source probe.

Official provider help:
https://eodhd.com/help/plans
https://eodhd.com/help/personal-use
https://eodhd.com/help/methodology

This is NOT a data licence, trading signal, research ranking or production
credential store. EODHD demo is evaluation-only. Free personal accounts have
provider-defined limits. Never upload data, token, ticker holdings or prices to
public Actions. Every network call is opt-in and bounded.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = "r004-eodhd-source-quality-pilot-v1"
DEMO_SYMBOL = "AAPL.US"
BASE = "https://eodhd.com/api"
MAX_BYTES = {"eod": 180_000, "splits": 50_000, "div": 90_000}
FIELDS = frozenset({"date", "open", "high", "low", "close",
                    "adjusted_close", "volume"})
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9._-]{1,29}")
SPLIT = re.compile(r"([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)")


def _unique(pairs):
    data = {}
    for k, v in pairs:
        if k in data:
            raise ValueError("Duplicate field in market source")
        data[k] = v
    return data


def _illegal_constant(_):
    raise ValueError("Nonfinite market-data number")


def _parse_array(payload: bytes, limit: int):
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= limit:
        raise ValueError("Missing or oversized provider response")
    try:
        obj = json.loads(payload, object_pairs_hook=_unique,
                         parse_float=Decimal, parse_int=Decimal,
                         parse_constant=_illegal_constant)
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Invalid provider JSON or entitlement error") from None
    if not isinstance(obj, list):
        raise ValueError("Provider response must be a documented JSON array")
    return obj


def _decimal(x, *, allow_zero=False):
    if type(x) not in (int, float, Decimal, str):
        raise ValueError("Invalid numeric provider field")
    try:
        d = Decimal(str(x))
    except (InvalidOperation, ValueError):
        raise ValueError("Malformed provider number") from None
    if not d.is_finite() or d < 0 or (d == 0 and not allow_zero):
        raise ValueError("Nonpositive or nonfinite provider number")
    return d


def _session(s, as_of):
    if not isinstance(s, str):
        raise ValueError("Missing source trading date")
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise ValueError("Malformed source trading date") from None
    if d > as_of:
        raise ValueError("Future source date")
    return d


def parse_eod(payload: bytes, *, as_of: date):
    rows = _parse_array(payload, MAX_BYTES["eod"])
    if not 1 <= len(rows) <= 400:
        raise ValueError("EOD source returned no rows or excessive history")
    seen, out = set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("Unexpected EOD bar schema")
        day = _session(row["date"], as_of)
        if day in seen or day.weekday() >= 5:
            raise ValueError("Duplicate or non-session EOD trading date")
        seen.add(day)
        op, hi, lo, close, adj, volume = (
            _decimal(row[key], allow_zero=(key == "volume"))
            for key in ("open", "high", "low", "close", "adjusted_close", "volume")
        )
        if lo > min(op, close) or hi < max(op, close) or lo > hi:
            raise ValueError("Invalid OHLC interval")
        out.append({"date": day, "open": op, "high": hi, "low": lo,
                    "close": close, "adjusted_close": adj, "volume": volume})
    out.sort(key=lambda r: r["date"])
    return out


def parse_splits(payload: bytes, *, as_of: date):
    rows = _parse_array(payload, MAX_BYTES["splits"])
    if len(rows) > 500:
        raise ValueError("Oversized split register")
    seen, output = set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"date", "split"}:
            raise ValueError("Unexpected split row schema")
        d = _session(row["date"], as_of)
        m = SPLIT.fullmatch(str(row["split"]))
        if not m:
            raise ValueError("Malformed split factor")
        if d in seen:
            raise ValueError("Duplicate split event date")
        factor = _decimal(m[1])/_decimal(m[2])
        if not Decimal(".001") <= factor <= Decimal("1000"):
            raise ValueError("Out-of-range split factor")
        seen.add(d)
        output.append({"date": d, "ratio": factor})
    return sorted(output, key=lambda r: r["date"])


def parse_dividends(payload: bytes, *, as_of: date, currency='USD'):
    rows = _parse_array(payload, MAX_BYTES["div"])
    if len(rows) > 1000:
        raise ValueError("Oversized dividend register")
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not {
            "date", "value", "unadjustedValue", "currency"
        }.issubset(row):
            raise ValueError("Unexpected dividend row schema")
        day = _session(row["date"], as_of)
        if day in seen or row["currency"] != currency:
            raise ValueError("Duplicate dividend or wrong payout currency")
        seen.add(day)
        out.append({"date": day,
                    "adjusted_per_share": _decimal(row["value"], allow_zero=True),
                    "original_per_share": _decimal(row["unadjustedValue"], allow_zero=True)})
    return sorted(out, key=lambda r: r["date"])


def assess(eod_raw: bytes, splits_raw: bytes, dividends_raw: bytes,
           *, as_of: date, retrieved_at_utc: datetime):
    """Provider diagnostics only. Split-adjusted notional volume is NOT turnover.

    Correct a *price* for splits in the 61-session evaluation interval using
    declared provider events; reject extreme discontinuities and insufficient
    sessions. This does not independently certify source/corporate actions or
    rights, or promote the data into B's real-source scoring pipeline.
    """
    if (retrieved_at_utc.tzinfo is None
            or retrieved_at_utc.utcoffset() != timedelta(0)
            or retrieved_at_utc.date() < as_of):
        raise ValueError("Retrieval timestamp must be UTC and >= as_of")
    prices = parse_eod(eod_raw, as_of=as_of)
    splits = parse_splits(splits_raw, as_of=as_of)
    dividends = parse_dividends(dividends_raw, as_of=as_of)
    if len(prices) < 61:
        raise ValueError("Insufficient 61-session real provider data")
    last = prices[-61:]
    last_start = last[0]["date"]
    split_window = [s for s in splits if last_start <= s["date"] <= last[-1]["date"]]
    dividend_window = [d for d in dividends if last_start <= d["date"] <= last[-1]["date"]]
    adjusted = []
    for row in last:
        factor = Decimal(1)
        for event in split_window:
            if row["date"] < event["date"]:
                factor *= event["ratio"]
        adjusted.append(row["close"]/factor)
    moves = [abs(adjusted[i]/adjusted[i-1]-1)
             for i in range(1, len(adjusted))]
    # Compare actual venue sessions via the existing checked exchange calendar.
    from .market_calendar import session
    start, end = last[0]["date"], last[-1]["date"]
    expected = [start + timedelta(days=i)
                for i in range((end-start).days+1)
                if session(start + timedelta(days=i), "XNAS")]
    if [r["date"] for r in last] != expected:
        raise ValueError("Missing/extra XNAS EOD sessions in last 61")
    if max(moves) >= Decimal(".15"):
        raise ValueError("Extreme price jump/corporate action unresolved")
    return {
        "schema_version": SCHEMA,
        "source_provider": "EODHD_API_DEMO_ONLY",
        "symbol": DEMO_SYMBOL,
        "source_as_of": as_of.isoformat(),
        "retrieved_at_utc": retrieved_at_utc.isoformat(),
        "first_session_61": start.isoformat(),
        "last_session": end.isoformat(),
        "available_eod_sessions": len(prices),
        "last_61_contiguous_nasdaq_sessions": True,
        "split_events_61": len(split_window),
        "dividend_events_61": len(dividend_window),
        "historical_volume_basis": "SPLIT_ADJUSTED_PROVIDER_DEFINITION",
        "ohlc_basis": "RAW_AS_TRADED",
        "adjusted_close_basis": "PROVIDER_SPLIT_AND_DIVIDEND_ADJUSTED",
        "cross_provider_actions_reconciled": False,
        "license_validated_for_private_production": False,
        "demo_data_not_trade_ready": True,
        "market_price_score": None,
        "underlying_issuer_isin_venue_verified": False,
        "price_snapshot_sha256": hashlib.sha256(eod_raw).hexdigest(),
        "splits_snapshot_sha256": hashlib.sha256(splits_raw).hexdigest(),
        "dividends_snapshot_sha256": hashlib.sha256(dividends_raw).hexdigest(),
    }


def _fetch(kind, symbol, start, end, token, *, opener):
    if kind not in MAX_BYTES or not SYMBOL.fullmatch(symbol):
        raise ValueError("Only allowlisted EODHD endpoint and symbol")
    params = urllib.parse.urlencode({
        "api_token": token, "from": start.isoformat(),
        "to": end.isoformat(), "fmt": "json",
        **({"period": "d"} if kind == "eod" else {})
    })
    url = f"{BASE}/{kind}/{symbol}?{params}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "InvestmentResearch-SourceValidation/1.0"})
    with opener.open(request, timeout=18) as reply:
        if reply.geturl().split("?")[0] != url.split("?")[0]:
            raise ValueError("Redirected or mismatched EODHD source")
        return reply.read(MAX_BYTES[kind]+1)


def run_demo(*, as_of: date, live_confirm=False, opener=None):
    if live_confirm is not True:
        raise ValueError("An explicit source demo request is required")
    if as_of > datetime.now(timezone.utc).date():
        raise ValueError("Future as_of disallowed")
    if not isinstance(as_of, date) or as_of.year != 2026:
        raise ValueError("Current Decision-2026 demo date required")
    # The free DEMO token is public/evaluation-only, never a production secret.
    if opener is None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ValueError("EODHD source redirects refused")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect())
    # Fixed small sample: independent stock picked for provider diagnostics,
    # not an investment recommendation or tactical candidate.
    start = max(date(2026, 7, 1), as_of - timedelta(days=180))
    payloads = {}
    for kind in ("eod", "splits", "div"):
        try:
            payloads[kind] = _fetch(kind, DEMO_SYMBOL, start, as_of,
                                    "demo", opener=opener)
        except (OSError, TimeoutError, urllib.error.HTTPError):
            raise ValueError("Provider unreachable or DEMO entitlement unavailable") from None
    return assess(payloads["eod"], payloads["splits"], payloads["div"],
                  as_of=as_of, retrieved_at_utc=datetime.now(timezone.utc))
