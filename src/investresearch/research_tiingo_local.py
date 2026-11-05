"""Tiingo Starter personal EOD: bounded, local split-adjusted research adapter.

Tiingo's EOD JSON contains RAW close, adjusted close (split/dividend),
splitFactor effective on event date, adjVolume (split-adjusted), and divCash.
This adapter reconstructs split-adjusted RAW closes for return and liquidity
proxies while retaining the vendor's adjustment disclaimer. No real trade,
price rights certification, issuer identity inference, or remote API use.

Docs: https://www.tiingo.com/documentation/end-of-day
Usage: https://www.tiingo.com/pricing
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin

PROVIDER = "TIINGO_EOD_PERSONAL_RESEARCH"
ATTESTATION = "PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED"
MAPPING = "TWO_SOURCE_ISIN_SYMBOL_VENUE_MANUALLY_REVIEWED"
MAX_BYTES = 250_000
MAX_ROWS = 400
SYMBOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,29}")
REQUIRED = {
    "date", "open", "high", "low", "close", "volume",
    "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume",
    "divCash", "splitFactor",
}
VENUES = {"XNAS", "XNYS"}


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise ValueError("Duplicate Tiingo source field")
        out[k] = v
    return out


def _not_finite(_):
    raise ValueError("NaN/Infinity in market source")


def _num(value, zero=False):
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing Tiingo numeric field")
    try:
        x = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError("Malformed Tiingo numeric field") from None
    if not x.is_finite() or x < 0 or (x == 0 and not zero):
        raise ValueError("Nonpositive/invalid Tiingo numeric field")
    return x


def _day(raw, as_of):
    if not isinstance(raw, str):
        raise ValueError("Missing Tiingo session date")
    try:
        if "T" in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
                raise ValueError("Tiingo timestamp not UTC")
            d = dt.date()
        else:
            d = date.fromisoformat(raw)
    except ValueError:
        raise ValueError("Invalid Tiingo UTC session date") from None
    if d > as_of or d.weekday() >= 5:
        raise ValueError("Future/weekend Tiingo session date")
    return d


def parse_tiingo(payload, *, as_of):
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("Missing/oversized Tiingo source")
    try:
        data = json.loads(payload, parse_float=Decimal, parse_int=Decimal,
                          object_pairs_hook=_pairs, parse_constant=_not_finite)
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Invalid Tiingo JSON/entitlement response") from None
    if not isinstance(data, list) or not 1 <= len(data) <= MAX_ROWS:
        raise ValueError("Tiingo price source needs a bounded list")
    out, seen = [], set()
    for r in data:
        if not isinstance(r, dict) or not REQUIRED.issubset(r):
            raise ValueError("Tiingo EOD schema incompatible")
        d = _day(r["date"], as_of)
        if d in seen:
            raise ValueError("Duplicate Tiingo session")
        seen.add(d)
        op, hi, lo, cl, vol, adjcl, adjvol, div, factor = (
            _num(r[k], zero=k in ("volume","adjVolume","divCash"))
            for k in ("open","high","low","close","volume","adjClose",
                      "adjVolume","divCash","splitFactor")
        )
        adjop, adjhi, adjlo = (_num(r[k]) for k in
                               ("adjOpen","adjHigh","adjLow"))
        if (lo > min(op,cl) or hi < max(op,cl)
                or adjlo > min(adjop,adjcl) or adjhi < max(adjop,adjcl)):
            raise ValueError("Inconsistent Tiingo OHLC/adjusted OHLC")
        if not Decimal(".001") <= factor <= Decimal("1000"):
            raise ValueError("Unsupported split factor magnitude")
        out.append({
            "date": d, "close_raw": cl, "volume_raw":vol,
            "close_adj_totalreturn_vendor":adjcl,
            "volume_split_adjusted_vendor":adjvol,
            "div_cash":div, "split_factor":factor,
        })
    return sorted(out, key=lambda x:x["date"])


def _timestamp(raw, as_of):
    if not isinstance(raw, str):
        raise ValueError("Missing Tiingo retrieval timestamp")
    try:
        d = datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("Malformed Tiingo UTC retrieval timestamp") from None
    if d.tzinfo is None or d.utcoffset()!=timedelta(0) or d.date()>as_of:
        raise ValueError("Tiingo retrieval must be UTC and before as_of")
    return d


def normalize_private_tiingo(source, payload, as_of, asset, *, repo_root):
    if (not isinstance(source,dict) or source.get("provider") != PROVIDER
            or source.get("usage_attestation") != ATTESTATION
            or source.get("identity_evidence_status") != MAPPING):
        raise ValueError("Tiingo personal terms and two-source identity review required")
    if not isinstance(asset,dict) or not valid_isin(asset.get("isin","")):
        raise ValueError("Tiingo source requires an explicit valid ISIN")
    if (asset.get("venue") not in VENUES or asset.get("currency")!="USD"
            or source.get("isin")!=asset["isin"]
            or source.get("venue")!=asset["venue"]
            or source.get("currency")!="USD"):
        raise ValueError("Unsupported Tiingo venue/FX/ISIN mapping")
    symbol = source.get("symbol")
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid Tiingo provider symbol")
    url = source.get("source_url")
    if not isinstance(url,str):
        raise ValueError("Missing Tiingo source URL")
    part = urlsplit(url)
    if (part.scheme!="https" or part.hostname!="api.tiingo.com"
            or part.path!=f"/tiingo/daily/{symbol}/prices"
            or part.username or part.password or part.port
            or part.query or part.fragment):
        raise ValueError("Tiingo URL must be token-free official symbol endpoint")
    root = Path(repo_root).resolve()
    local = Path(source.get("path","")).expanduser().resolve()
    if local.is_relative_to(root) and not local.is_relative_to(root/"data/private"):
        raise ValueError("Tiingo private source file must be under data/private")
    acquired = _timestamp(source.get("retrieved_at_utc"), as_of)
    data = parse_tiingo(payload, as_of=as_of)
    if len(data)<61 or data[-1]["date"]>acquired.date():
        raise ValueError("Insufficient/late Tiingo historical EOD records")
    out = []
    for item in data:
        # Effective factor on date d: apply only splits strictly AFTER d.
        after = Decimal(1)
        for later in data:
            if item["date"] < later["date"]:
                after *= later["split_factor"]
        close = item["close_raw"]/after
        if not close.is_finite() or close <= 0:
            raise ValueError("Invalid Tiingo split-reconstructed close")
        out.append({"date": item["date"].isoformat(),
                    "close": str(close),
                    "volume": str(item["volume_split_adjusted_vendor"])})
    splits = [x["date"].isoformat() for x in data if x["split_factor"] != 1]
    return out, {
        "price_basis":"TIINGO_PROVIDER_SPLIT_ADJUSTED_CLOSE_NOT_TOTAL_RETURN",
        "volume_basis":"TIINGO_PROVIDER_SPLIT_ADJUSTED_VOLUME",
        "usage_rights_status":"USER_ASSERTED_PERSONAL_PRIVATE_ONLY_NOT_INDEPENDENTLY_LICENSED",
        "identity_mapping_status":MAPPING+"_NOT_INDEPENDENTLY_AUTHENTICATED",
        "split_dates":splits,
        "source_dividend_event_count":sum(x["div_cash"]!=0 for x in data),
        "corporate_actions_verified_by_independent_source":False,
        "data_warning":"Vendor composite data: personal-only, US EOD, no quotes or independently verified entitlements",
    }
