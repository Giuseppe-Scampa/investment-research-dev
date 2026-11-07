"""R-004/R-005: manually obtained Euronext Milan/Paris history CSV.

Original bytes and declared export settings are checked, not licensed or
authenticated by the engine. No website scraping, API, login, paid history,
corporate-action imputation, price conversion, quotes or trading.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin

PROVIDER = "EURONEXT_PERSONAL_HISTORY_FILE"
MAX_BYTES = 5_000_000
MAX_SESSIONS = 5000
MARKET_TO_VENUE = {
    "MTAA": "XMIL",  # Euronext Milan equities
    "ETFP": "XMIL",  # Borsa Italiana ETFplus
    "EXGM": "XMIL",  # Euronext Growth Milan
    "ETLX": "XMIL",  # EuroTLX; price unit must be verified for each asset
    "XPAR": "XPAR",  # Euronext Paris
}
ASSET_TYPES = {"EQUITY", "ETF_UCITS", "ETC", "ETN", "CERTIFICATE"}
FIELDS = {"date", "close", "volume"}
DATE_FORMATS = {"ISO", "DMY_4_SLASH", "DMY_2_SLASH", "MDY_2_SLASH", "DMY_4_DOT"}
PRICE_BASIS_ADJUSTED = "EURONEXT_OPERATOR_SELECTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED"
PRICE_BASIS_UNADJUSTED = "EURONEXT_OPERATOR_SELECTED_UNADJUSTED_NEEDS_CORPORATE_ACTION_REVIEW"
ATTESTATION = "EURONEXT_PERSONAL_NONCOMMERCIAL_LOCAL_USE_ACKNOWLEDGED"


def _date(raw,fmt):
    if not isinstance(raw,str):
        raise ValueError("Missing Euronext CSV date")
    value=raw.strip()
    if fmt=="ISO":
        return date.fromisoformat(value)
    patterns={
        "DMY_4_SLASH":"%d/%m/%Y", "DMY_2_SLASH":"%d/%m/%y",
        "MDY_2_SLASH":"%m/%d/%y", "DMY_4_DOT":"%d.%m.%Y",
    }
    if fmt not in patterns:
        raise ValueError("Unknown Euronext date format")
    return datetime.strptime(value,patterns[fmt]).date()


def _decimal(raw,*,decimal_separator,thousands_separator,positive):
    if not isinstance(raw,str):
        raise ValueError("Euronext original CSV numeric value missing")
    original=raw.strip()
    if decimal_separator not in (".",",") or thousands_separator not in ("", " ", ".", ","):
        raise ValueError("Euronext numeric locale must be explicit")
    if thousands_separator==decimal_separator:
        raise ValueError("Ambiguous Euronext decimal/thousands separator")
    dec=re.escape(decimal_separator)
    if thousands_separator:
        sep=re.escape(thousands_separator)
        pattern=rf"(?:[0-9]{{1,3}}(?:{sep}[0-9]{{3}})+|[0-9]+)(?:{dec}[0-9]+)?"
    else:
        pattern=rf"[0-9]+(?:{dec}[0-9]+)?"
    if not re.fullmatch(pattern,original):
        raise ValueError("Malformed Euronext price/volume or ambiguous locale")
    normalized=original.replace(thousands_separator,"") if thousands_separator else original
    normalized=normalized.replace(decimal_separator,".")
    try:
        number=Decimal(normalized)
    except InvalidOperation:
        raise ValueError("Euronext number is not a finite decimal") from None
    if not number.is_finite() or number<0 or (positive and number==0):
        raise ValueError("Euronext price must be positive; volume nonnegative")
    return number


def normalize_private_euronext(meta,payload,as_of,asset,*,repo_root):
    """Parse one original Euronext historical CSV into date,close,volume rows.

    Does not prove adjusted-price basis, source authenticity, licence validity,
    ISIN legal class or corporate-action correctness.
    """
    if not isinstance(meta,dict) or meta.get("provider")!=PROVIDER:
        raise ValueError("Original Euronext provider code required")
    if (not isinstance(asset,dict) or not valid_isin(asset.get("isin",""))
            or asset.get("asset_type") not in ASSET_TYPES
            or asset.get("currency")!="EUR"):
        raise ValueError("Euronext instrument must have explicit ISIN, EUR and supported legal class")
    market=meta.get("source_market_code")
    if market not in MARKET_TO_VENUE or asset.get("venue")!=MARKET_TO_VENUE[market]:
        raise ValueError("Unsupported Euronext market segment / exchange venue crosswalk")
    if market=="ETLX" and asset["asset_type"]=="CERTIFICATE":
        # Often quoted as unit price, but not always; payoff and leverage
        # are NEVER inferred from a displayed close.
        if meta.get("close_unit_operator_asserted")!="EUR_PER_CERTIFICATE_UNIT":
            raise ValueError("EuroTLX certificate needs explicit price unit evidence")
    if meta.get("download_page_isin")!=asset["isin"] or not valid_isin(
            meta.get("download_page_isin","")):
        raise ValueError("Euronext export ISIN must equal the researched instrument ISIN")
    url=meta.get("source_url")
    if not isinstance(url,str) or len(url)>600:
        raise ValueError("Euronext original historical-download page URL required")
    u=urlsplit(url)
    exact=f"/{asset['isin']}-{market}"
    if (u.scheme!="https" or u.hostname!="live.euronext.com"
            or u.port is not None or u.username or u.password or u.query or u.fragment
            or u.path not in (
                "/en/popout-page/getHistoricalPrice"+exact,
                "/it/popout-page/getHistoricalPrice"+exact)):
        raise ValueError("Euronext official ISIN+market-specific history page mismatch")
    if meta.get("usage_attestation")!=ATTESTATION:
        raise ValueError("Explicit Euronext noncommercial local-use consent required")
    if meta.get("data_rights_independently_verified") is not False:
        raise ValueError("Provider data rights cannot be certified by this parser")
    if not isinstance(payload,bytes) or not 0<len(payload)<=MAX_BYTES:
        raise ValueError("Original Euronext CSV missing or oversized")
    if meta.get("sha256")!=hashlib.sha256(payload).hexdigest():
        raise ValueError("Original Euronext CSV SHA-256 mismatch")
    stamp=meta.get("retrieved_at_utc")
    if not isinstance(stamp,str):
        raise ValueError("Original Euronext download UTC timestamp mandatory")
    try:
        retrieved=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("Invalid Euronext download UTC timestamp") from None
    if retrieved.tzinfo is None or retrieved.utcoffset()!=timedelta(0) or retrieved.date()>as_of:
        raise ValueError("Euronext original CSV must be acquired in UTC no later than as-of")
    export=meta.get("export_adjustment")
    if export not in ("ADJUSTED","NON_ADJUSTED"):
        raise ValueError("Explicit Euronext Adjusted/Non-Adjusted selection required")
    if meta.get("base_100_export") is not False:
        raise ValueError("Base-100 normalized export cannot provide original EUR close")
    flags=meta.get("adjustments_claimed")
    if (not isinstance(flags,dict)
            or set(flags)!={"splits","dividends","subscription_rights"}
            or any(type(v) is not bool for v in flags.values())):
        raise ValueError("Every claimed corporate-action correction must be an explicit boolean")
    mapping=meta.get("columns")
    if (not isinstance(mapping,dict) or set(mapping)!=FIELDS
            or any(not isinstance(v,str) or not v or len(v)>100 for v in mapping.values())
            or len(set(mapping.values()))!=3):
        raise ValueError("Explicit Euronext CSV date/close/volume columns required")
    delimiter=meta.get("delimiter")
    if delimiter not in (",",";","\t"):
        raise ValueError("Euronext CSV delimiter must be explicitly declared")
    encoding=meta.get("encoding")
    if encoding not in ("utf-8-sig","cp1252"):
        raise ValueError("Unsupported original Euronext CSV character encoding")
    date_format=meta.get("date_format")
    if date_format not in DATE_FORMATS:
        raise ValueError("Original Euronext CSV date locale required")
    decimal_sep=meta.get("decimal_separator")
    thousands_sep=meta.get("thousands_separator")
    if decimal_sep not in (".",",") or thousands_sep not in ("",".",","," "):
        raise ValueError("Euronext numeric locale required")
    try:
        text=payload.decode(encoding)
    except UnicodeError:
        raise ValueError("Original Euronext CSV could not be decoded in claimed locale") from None
    reader=csv.DictReader(io.StringIO(text),delimiter=delimiter)
    if reader.fieldnames is None or set(reader.fieldnames)!=set(mapping.values()):
        raise ValueError("Euronext CSV headers differ from explicit mapping")
    out=[];seen=set()
    for raw in reader:
        if None in raw or any(v is None for v in raw.values()):
            raise ValueError("Malformed Euronext historical CSV row")
        when=_date(raw[mapping["date"]],date_format)
        if when>retrieved.date():
            raise ValueError("Historical Euronext price follows original download timestamp")
        if when>as_of:
            raise ValueError("Euronext export contains future price relative to cutoff")
        if when in seen:
            raise ValueError("Duplicate Euronext historical price session")
        seen.add(when)
        price=_decimal(raw[mapping["close"]],decimal_separator=decimal_sep,
                       thousands_separator=thousands_sep,positive=True)
        volume=_decimal(raw[mapping["volume"]],decimal_separator=decimal_sep,
                        thousands_separator=thousands_sep,positive=False)
        out.append({"date":when.isoformat(),"close":str(price),"volume":str(volume)})
        if len(out)>MAX_SESSIONS:
            raise ValueError("Euronext source exceeds bounded daily series cap")
    if not out:
        raise ValueError("No original Euronext dated price rows")
    out.sort(key=lambda x:x["date"])
    complete=(export=="ADJUSTED" and all(flags.values()))
    basis=(PRICE_BASIS_ADJUSTED if complete else PRICE_BASIS_UNADJUSTED)
    return out,{
        "price_basis":basis,
        "euronext_original_source_sha256":meta["sha256"],
        "euronext_source_market_code":market,
        "euronext_isin_operator_confirmed":asset["isin"],
        "euronext_adjustment_export_selection":export,
        "euronext_adjustment_flags_operator_declared":flags,
        "euronext_data_verified_from_exchange":False,
        "euronext_historic_corporate_actions_independently_verified":False,
        "euronext_data_rights_independently_verified":False,
        "usage_rights_status":"EURONEXT_LOCAL_PERSONAL_USE_OPERATOR_ASSERTED_NOT_AUTHENTICATED",
        "euronext_price_not_broker_executable_quote":True,
    }
