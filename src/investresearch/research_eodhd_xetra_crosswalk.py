"""R-006: two-independent-reference ISIN/currency crosswalk for Xetra/EODHD.

Identity coverage only, NOT a provider price request, broker venue,
corporate action guarantee, instrument tax type or paid-data entitlement.
Never store vendor raw reference in public git. Provider exchange list docs:
https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin
from .research_xetra_universe import parse_xetra, _retrieved, _safe_cell

PROVIDER = "EODHD_XETRA_SYMBOL_REFERENCE"
SCHEMA = "r006-xetra-eodhd-identity-coverage-v1"
MAX_BYTES = 8_000_000
MAX_ROWS = 100_000
RAW_TYPES = {
    "Common Stock": "CS",
    "ETF": "ETF",
    "ETC": "ETC",
    "ETN": "ETN",
}
FIELDS = [
    "isin", "venue", "currency", "xetra_mnemonic",
    "eodhd_symbol", "xetra_source_type", "eodhd_source_type",
    "research_status",
]


def parse_eodhd_xetra_catalog(raw: bytes, meta: dict, *, as_of: date):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Missing/oversized EODHD exchange reference")
    if not isinstance(meta, dict) or meta.get("provider") != PROVIDER:
        raise ValueError("Explicit EODHD reference provider required")
    url = meta.get("source_url")
    if not isinstance(url, str):
        raise ValueError("Missing source URL")
    u = urlsplit(url)
    if (u.scheme != "https" or u.hostname != "eodhd.com"
            or u.path != "/api/exchange-symbol-list/XETRA"
            or u.port or u.username or u.password or u.query or u.fragment):
        raise ValueError("Catalog must originate from official token-free URL")
    if meta.get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("EODHD source SHA256 discrepancy")
    retrieved = _retrieved(meta.get("retrieved_at_utc"))
    if retrieved.date() > as_of:
        raise ValueError("EODHD source acquired after as-of")
    if meta.get("usage_attestation") != "PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED":
        raise ValueError("Catalog private personal-use rights acknowledgement required")
    try:
        rows = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid provider catalog JSON") from None
    if not isinstance(rows, list) or len(rows) > MAX_ROWS or not rows:
        raise ValueError("Catalog expected bounded array")
    fields = {"Code", "Name", "Country", "Exchange", "Currency", "Type", "Isin"}
    result, seen = [], set()
    skipped = Counter()
    for row in rows:
        if not isinstance(row, dict) or not fields.issubset(row):
            raise ValueError("EODHD reference schema drift")
        if row["Exchange"] not in ("XETRA", "XETR"):
            skipped["EXCHANGE_OUTSIDE_XETRA"] += 1
            continue
        if not isinstance(row["Isin"], str) or not valid_isin(row["Isin"]):
            skipped["ISIN_MISSING_OR_INVALID"] += 1
            continue
        code, currency = row["Code"], row["Currency"]
        if (not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,30}",code)
                or not isinstance(currency,str) or
                not re.fullmatch(r"[A-Z]{3}",currency)):
            raise ValueError("Invalid Xetra provider ticker/currency")
        identity = (row["Isin"], code, currency)
        if identity in seen:
            raise ValueError("Duplicated EODHD vendor listing")
        seen.add(identity)
        result.append({
            "isin":row["Isin"],
            "currency":currency,
            "symbol":code + ".XETRA",
            "source_type":row["Type"] if isinstance(row["Type"],str) else "UNKNOWN",
        })
    return result, {
        "provider":PROVIDER, "source_raw_sha256":hashlib.sha256(raw).hexdigest(),
        "retrieved_at_utc":retrieved.isoformat(),
        "total_vendor_rows":len(rows),
        "usable_isin_vendor_rows":len(result),
        "skipped_vendor":dict(sorted(skipped.items())),
    }


def _unique(pairs):
    out={}
    for key,value in pairs:
        if key in out:
            raise ValueError("Duplicate provider field")
        out[key]=value
    return out


def join_xetra_eodhd(xetra, xetra_manifest, catalog, catalog_manifest):
    if (xetra_manifest.get("candidate_count") != len(xetra)
            or xetra_manifest.get("provider")!="XETRA_T7_INSTRUMENT_REFERENCE"
            or catalog_manifest.get("provider")!=PROVIDER):
        raise ValueError("Both original source manifests required")
    byidentity=defaultdict(list)
    for item in catalog:
        if not valid_isin(item["isin"]):
            raise ValueError("Catalog ISIN invalid")
        byidentity[(item["isin"],item["currency"])].append(item)
    out=[]
    counts=Counter()
    for item in xetra:
        matches=byidentity.get((item["isin"],item["currency"]),[])
        if not matches:
            counts["NO_PROVIDER_ISIN_CURRENCY_MATCH"] += 1
            continue
        if len(matches)!=1:
            counts["DUPLICATE_ISIN_VENDOR_LISTINGS_NEED_REVIEW"] += 1
            continue
        match=matches[0]
        if RAW_TYPES.get(match["source_type"])!=item["source_instrument_type"]:
            counts["ASSET_CLASS_DISAGREEMENT_NEEDS_REVIEW"] += 1
            continue
        counts["CROSS_SOURCE_ISIN_CURRENCY_CLASS_MATCHED_UNCERTIFIED"] += 1
        out.append({
            "isin":item["isin"], "venue":item["venue"],
            "currency":item["currency"],
            "xetra_mnemonic":item["mnemonic"],
            "eodhd_symbol":match["symbol"],
            "xetra_source_type":item["source_instrument_type"],
            "eodhd_source_type":match["source_type"],
            "research_status":"TWO_REFERENCE_COVERAGE_MATCHED_NOT_TRADE_READY",
        })
    audit={
        "schema_version":SCHEMA,
        "xetra_reference_sha256":xetra_manifest["source_raw_sha256"],
        "eodhd_reference_sha256":catalog_manifest["source_raw_sha256"],
        "xetra_active_reference_count":len(xetra),
        "matched_count":len(out),
        "coverage_pct":round(100*len(out)/len(xetra),2),
        "rejection_counts":dict(sorted(counts.items())),
        "status":"CROSS_SOURCE_IDENTITIES_FOR_PROVIDER_COVERAGE_NOT_RANKED",
        "first_price_source_gate":"61 approved sessions, provider terms, independent actions and correct MIC",
        "source_use_rights_independently_verified":False,
        "trade_ready":False,
    }
    return out,audit


def write_crosswalk(xetra_raw, xetra_meta, vendor_raw, vendor_meta, as_of, output,
                    *, repo_root):
    root=Path(repo_root).resolve()
    out=Path(output).resolve()
    if out.is_relative_to(root) and not out.is_relative_to(root/"data/private"):
        raise ValueError("Original vendor identity crosswalk must be private inside repo")
    if out.exists():
        raise ValueError("No overwrite of private source coverage")
    a,b=parse_xetra(Path(xetra_raw).read_bytes(),json.loads(Path(xetra_meta).read_text()),as_of=as_of)
    c,d=parse_eodhd_xetra_catalog(Path(vendor_raw).read_bytes(),json.loads(Path(vendor_meta).read_text()),as_of=as_of)
    entries,report=join_xetra_eodhd(a,b,c,d)
    out.mkdir(parents=True)
    buf=io.StringIO(newline="")
    writer=csv.DictWriter(buf,fieldnames=FIELDS,lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        writer.writerow({k:_safe_cell(entry[k]) for k in FIELDS})
    (out/"XETRA_EODHD_IDENTITY_COVERAGE.csv").write_text(buf.getvalue(),encoding="utf-8")
    (out/"XETRA_EODHD_CROSSWALK_AUDIT.json").write_text(
        json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    return report
