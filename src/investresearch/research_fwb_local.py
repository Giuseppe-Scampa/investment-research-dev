"""M3/R-004/R-005: manual official Deutsche Boerse FWB history CSV intake.

No website automation, scraping or paid API. Operator downloads a CSV with
explicit accepted non-commercial terms, chooses venue and corporate-action
options, and supplies original bytes + SHA-256. This parser checks structure
and provenance *claims* but never authenticates the exchange or adjustments.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from .quality import valid_isin
from .research_sources import sha256_bytes

PROVIDER="FWB_PERSONAL_HISTORY_FILE"
PRICE_BASIS="FWB_OPERATOR_ASSERTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED"
FIELDS={"date","close","volume"}
DATE_FORMATS={"ISO","DMY"}
MAX_SESSIONS=3000


def _number(value, *, separator, zero=False):
    if not isinstance(value,str):
        raise ValueError("Missing numeric FWB price field")
    raw=value.strip().replace(" ","")
    if separator=="comma":
        if not re.fullmatch(r"\d+(?:,\d+)?",raw):
            raise ValueError("FWB comma-decimal value malformed")
        raw=raw.replace(",",".")
    elif separator=="dot":
        if not re.fullmatch(r"\d+(?:\.\d+)?",raw):
            raise ValueError("FWB dot-decimal value malformed")
    else:
        raise ValueError("Unsupported FWB decimal separator")
    try:
        result=Decimal(raw)
    except InvalidOperation:
        raise ValueError("Malformed FWB price/volume amount") from None
    if not result.is_finite() or result<0 or (result==0 and not zero):
        raise ValueError("FWB close/volume must have valid nonnegative units")
    return result


def _day(value,fmt):
    if not isinstance(value,str):
        raise ValueError("FWB date missing")
    if fmt=="ISO":
        return date.fromisoformat(value.strip())
    if fmt=="DMY":
        return datetime.strptime(value.strip(),"%d.%m.%Y").date()
    raise ValueError("Unsupported FWB date format")


def normalize_private_fwb(meta, payload, as_of, asset, *, repo_root):
    """Return dated close/volume bars + a non-certifying source provenance.

    CSV headers have explicit operator mapping because UI exports may change.
    We do not infer values or columns, adjust corporate events, fill sessions,
    interpolate missing bars, or invent total return from unadjusted closes.
    """
    if meta.get("provider")!=PROVIDER:
        raise ValueError("FWB original CSV provider mismatch")
    if (meta.get("usage_attestation")!="FWB_NONCOMMERCIAL_PERSONAL_USE_ACCEPTED"
            or meta.get("downloaded_market_place")!="XETR"
            or asset.get("venue")!="XETR" or asset.get("currency")!="EUR"):
        raise ValueError("FWB noncommercial terms, Xetra EUR venue must be explicit")
    isin=meta.get("download_page_isin")
    if (not isinstance(isin,str) or not valid_isin(isin)
            or isin!=asset.get("isin")):
        raise ValueError("FWB source ISIN must exactly match the instrument")
    url=meta.get("source_url")
    if not isinstance(url,str) or len(url)>1500:
        raise ValueError("FWB original instrument page URL required")
    parts=urlsplit(url)
    if (parts.scheme!="https" or parts.hostname!="live.deutsche-boerse.com"
            or not parts.path.endswith("/price-history/historical-prices-and-volumes")
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError("Only original FWB historical prices page is supported")
    timestamp=meta.get("retrieved_at_utc")
    if not isinstance(timestamp,str):
        raise ValueError("FWB collection timestamp must be exact UTC")
    try:
        retrieved=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("FWB collection timestamp must be exact UTC") from None
    if (retrieved.tzinfo is None or retrieved.utcoffset()!=timedelta(0)
            or retrieved.date()>as_of):
        raise ValueError("FWB data snapshot must not be future or non-UTC")
    if meta.get("sha256")!=sha256_bytes(payload):
        raise ValueError("FWB original source SHA256 mismatch")
    adjustments=meta.get("adjustments_claimed")
    if (not isinstance(adjustments,dict) or
            set(adjustments)!={"splits","dividends","subscription_rights"} or
            any(type(v) is not bool for v in adjustments.values())):
        raise ValueError("FWB original adjustment checkbox declarations required")
    columns=meta.get("columns")
    if (not isinstance(columns,dict) or set(columns)!=FIELDS or
            any(not isinstance(v,str) or not v or len(v)>90 for v in columns.values())
            or len(set(columns.values()))!=3):
        raise ValueError("FWB CSV column names must be explicitly mapped")
    delimiter=meta.get("delimiter")
    if delimiter not in (",",";","\t"):
        raise ValueError("FWB delimiter must be explicitly approved")
    decimal=meta.get("decimal_separator")
    if decimal not in ("comma","dot"):
        raise ValueError("FWB decimal separator must be explicit")
    datefmt=meta.get("date_format")
    if datefmt not in DATE_FORMATS:
        raise ValueError("FWB date format must be explicit")
    if len(payload)>5_000_000:
        raise ValueError("FWB original CSV size exceeds manual intake cap")
    try:
        reader=csv.DictReader(io.StringIO(payload.decode("utf-8-sig")),delimiter=delimiter)
    except UnicodeError:
        raise ValueError("FWB CSV must be UTF-8 encoded") from None
    if reader.fieldnames is None or set(reader.fieldnames)!=set(columns.values()):
        raise ValueError("FWB header mismatch; never guess source columns")
    result=[]
    seen=set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("FWB malformed source CSV row")
        current=_day(row[columns["date"]],datefmt)
        if current>as_of:
            continue
        if current>retrieved.date():
            raise ValueError("FWB source contains prices after its retrieval date")
        if current in seen:
            raise ValueError("FWB duplicate source session")
        seen.add(current)
        price=_number(row[columns["close"]],separator=decimal)
        volume=_number(row[columns["volume"]],separator=decimal,zero=True)
        result.append({"date":current.isoformat(),"close":str(price),"volume":str(volume)})
        if len(result)>MAX_SESSIONS:
            raise ValueError("FWB historical sample exceeds bounded daily series")
    if not result:
        raise ValueError("FWB source has no usable historical sessions")
    result.sort(key=lambda r:r["date"])
    # Never silently assert all corrections happened simply because
    # checkboxes were clicked. A manually adjusted series is NOT independently
    # verified, and instrument level dividend/split history is not supplied.
    return result,{
        "price_basis":PRICE_BASIS if all(adjustments.values())
                      else "FWB_OPERATOR_SELECTED_PARTIAL_ADJUSTMENTS_NOT_VERIFIED",
        "usage_rights_status":"OPERATOR_ACCEPTED_NONCOMMERCIAL_FWB_TERMS_NOT_AUTHENTICATED",
        "adjustment_flags_operator_declared":adjustments,
        "original_source_sha256":meta["sha256"],
        "fwb_isin_operator_confirmed":isin,
        "fwb_market_place_operator_confirmed":"XETR",
        "fwb_data_verified_from_exchange":False,
        "historic_dividend_or_split_events_independently_verified":False,
    }
