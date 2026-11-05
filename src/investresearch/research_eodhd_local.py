"""R-004/R-005: private, explicitly authorised EODHD EOD source adapter.

This adapter consumes already-acquired local raw EOD/split/dividend JSON.
It *never downloads* data, derives an ISIN from a symbol, infers usage rights,
or confirms split/dividend accuracy beyond source-consistent event metadata.

EODHD base OHLC is raw, adjusted_close is split+dividend adjusted, and
volume is split-adjusted: the price used for turnover MUST be split-adjusted
raw close (no dividends), NOT adjusted_close or raw close across a split.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin
from .research_eodhd_pilot import (
    parse_eod, parse_splits, parse_dividends, SYMBOL,
)

PROVIDER = "EODHD_EOD_PERSONAL_RESEARCH"
SPLIT_PROVIDER = "EODHD_PERSONAL_SPLITS"
DIVIDEND_PROVIDER = "EODHD_PERSONAL_DIVIDENDS"
ATTESTATION = "PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED"
MAPPING = "TWO_SOURCE_ISIN_SYMBOL_VENUE_MANUALLY_REVIEWED"
MAX_SUPPORT_BYTES = 100_000
VENUE_TO_EXCHANGE = {
    "XETR": "XETRA",
    "XPAR": "PA",
    "XNAS": "US",
    "XNYS": "US",
}
SUPPORTED_CURRENCY = {"EUR", "USD"}


def _url_matches(value, kind, symbol):
    if not isinstance(value, str):
        return False
    u = urlsplit(value)
    return (u.scheme == "https" and u.hostname == "eodhd.com"
            and u.path == f"/api/{kind}/{symbol}"
            and not (u.username or u.password or u.port or u.query or u.fragment))


def _timestamp(value, cutoff):
    if not isinstance(value, str):
        raise ValueError("Missing UTC source acquisition timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Malformed UTC source acquisition timestamp") from None
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0) or dt.date() > cutoff:
        raise ValueError("Acquisition must be dated UTC no later than research as_of")
    return dt


def _private_path(path, root):
    full = Path(path).expanduser().resolve()
    repo = Path(root).resolve()
    if full.is_relative_to(repo) and not full.is_relative_to(repo / "data/private"):
        raise ValueError("EODHD source files in a repository must stay under data/private/")
    return full


def _read_action(meta, *, kind, symbol, as_of, retrieved, repo_root):
    expected = SPLIT_PROVIDER if kind == "splits" else DIVIDEND_PROVIDER
    if not isinstance(meta, dict) or meta.get("provider") != expected:
        raise ValueError("Missing official split/dividend event source declaration")
    if not _url_matches(meta.get("source_url"), kind, symbol):
        raise ValueError("Corporate-action URL/symbol is inconsistent")
    rawpath = _private_path(meta.get("path", ""), repo_root)
    if not rawpath.is_file() or not 0 < rawpath.stat().st_size <= MAX_SUPPORT_BYTES:
        raise ValueError("Missing or oversized corporate-action snapshot")
    payload = rawpath.read_bytes()
    if meta.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError("Corporate-action SHA-256 mismatch")
    acquired = _timestamp(meta.get("retrieved_at_utc"), as_of)
    if acquired.date() < retrieved.date():
        raise ValueError("EODHD action register is older than EOD prices")
    return payload


def normalize_private_eodhd(source, raw_eod, as_of, asset, *, repo_root):
    """Return (normalized daily date/close/volume rows, audit-only metadata).

    An explicit manual two-source ISIN/venue review is required; the engine
    still cannot independently certify mappings or broker availability.
    """
    if (not isinstance(source, dict) or source.get("provider") != PROVIDER
            or source.get("usage_attestation") != ATTESTATION):
        raise ValueError("EODHD local personal-use rights attestation required")
    if not isinstance(asset, dict) or not valid_isin(asset.get("isin","")):
        raise ValueError("EODHD price series must bind to valid source ISIN")
    symbol = source.get("symbol", "")
    venue, currency = asset.get("venue"), asset.get("currency")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid provider symbol")
    if venue not in VENUE_TO_EXCHANGE or currency not in SUPPORTED_CURRENCY:
        raise ValueError("Unsupported EODHD venue/currency")
    if not symbol.endswith("." + VENUE_TO_EXCHANGE[venue]):
        raise ValueError("EODHD symbol exchange suffix disagrees with venue")
    if not _url_matches(source.get("source_url"), "eod", symbol):
        raise ValueError("EODHD price URL contains mismatched symbol, host or credentials")
    if source.get("identity_evidence_status") != MAPPING:
        raise ValueError("Explicit two-source ISIN/venue mapping review required")
    if (source.get("isin") != asset["isin"] or
            source.get("venue") != venue or
            source.get("currency") != currency):
        raise ValueError("Provider mapping does not match research identity")
    if not isinstance(raw_eod, bytes):
        raise ValueError("Expected original raw EOD JSON bytes")
    _private_path(source.get("path", ""), repo_root)
    retrieved = _timestamp(source.get("retrieved_at_utc"), as_of)
    prices = parse_eod(raw_eod, as_of=as_of)
    if len(prices) < 61:
        raise ValueError("At least 61 original dated EOD rows required")
    if prices[-1]["date"] > retrieved.date():
        raise ValueError("EOD prices postdate declared source acquisition")

    splitraw = _read_action(source.get("splits_source"), kind="splits",
                            symbol=symbol, as_of=as_of, retrieved=retrieved,
                            repo_root=repo_root)
    dividendsraw = _read_action(source.get("dividends_source"), kind="div",
                               symbol=symbol, as_of=as_of, retrieved=retrieved,
                               repo_root=repo_root)
    splits = parse_splits(splitraw, as_of=as_of)
    dividends = parse_dividends(dividendsraw, as_of=as_of, currency=currency)
    # EOD price rows are raw historical close; provider volume already split
    # adjusted. Reconstruct one consistent current-share-count price basis.
    # A split on d becomes effective ON d, so only events AFTER d apply.
    output = []
    for row in prices:
        later = Decimal(1)
        for event in splits:
            if row["date"] < event["date"] <= prices[-1]["date"]:
                later *= event["ratio"]
        close = row["close"] / later
        if not close.is_finite() or close <= 0:
            raise ValueError("Invalid reconstructed split-adjusted source close")
        output.append({"date":row["date"].isoformat(),
                       "close":str(close), "volume":str(row["volume"])})
    # Metadata is source supplied and an operator attestation, NOT verified
    # market-data entitlement or corporate action accuracy.
    notes = {
        "price_basis": "EODHD_PROVIDER_SPLIT_ADJUSTED_CLOSE_NOT_TOTAL_RETURN",
        "volume_basis": "EODHD_PROVIDER_SPLIT_ADJUSTED_VOLUME",
        "usage_rights_status": "USER_ASSERTED_PERSONAL_LOCAL_ONLY_NOT_INDEPENDENTLY_LICENSED",
        "identity_mapping_status": MAPPING + "_NOT_INDEPENDENTLY_AUTHENTICATED",
        "split_dates": [x["date"].isoformat() for x in splits],
        "split_source_sha256": hashlib.sha256(splitraw).hexdigest(),
        "dividend_source_sha256": hashlib.sha256(dividendsraw).hexdigest(),
        "source_dividend_event_count": len(dividends),
        "corporate_actions_verified_by_independent_source": False,
        "data_warning": "Not total return; not an executable quote; source rights are self-attested",
    }
    return output, notes
