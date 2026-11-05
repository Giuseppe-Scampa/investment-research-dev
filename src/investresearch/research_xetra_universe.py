"""Offline, unranked Xetra T7 multi-asset instrument discovery.

The public Xetra instrument reference file identifies listed instruments,
not prices, portfolio eligibility, UCITS legal status, tax, ethical exposure,
or investment opportunities. No network access and no implicit license grant.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin

PROVIDER = "XETRA_T7_INSTRUMENT_REFERENCE"
SCHEMA = "r006-xetra-discovery-v1"
MAX_BYTES = 20_000_000
MAX_ROWS = 100_000
SOURCE_NAME = "t7-xetr-allTradableInstruments.csv"
TYPES = {
    "CS": "EQUITY",
    "ETF": "ETF_LEGAL_STATUS_UNVERIFIED",
    "ETC": "ETC",
    "ETN": "ETN",
    "BOND": "BOND_UNCLASSIFIED",
    "WAR": "WARRANT_LEGAL_TAX_STATUS_UNVERIFIED",
    "OTHER": "OTHER_UNCLASSIFIED",
    "SR": "SUBSCRIPTION_RIGHT",
    "FUN": "FUND_UNCLASSIFIED",
}
FIELDS = ("isin", "instrument", "mnemonic", "venue", "currency",
          "source_instrument_type", "asset_type", "status")
REQUIRED = {
    "Product Status", "Instrument Status", "Instrument", "ISIN",
    "Mnemonic", "MIC Code", "Settlement Currency", "Instrument Type",
}


def _retrieved(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("Source retrieval requires explicit UTC timestamp")
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Malformed retrieval timestamp") from None
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("Retrieval timestamp must be UTC")
    return result


def _official_url(url: str) -> bool:
    try:
        u = urlsplit(url)
    except ValueError:
        return False
    return (
        u.scheme == "https" and
        u.hostname in {"www.cashmarket.deutsche-boerse.com",
                       "cashmarket.deutsche-boerse.com", "www.xetra.com"} and
        not (u.username or u.password or u.query or u.fragment or u.port) and
        bool(re.fullmatch(
            r"/resource/blob/[0-9]+/[0-9a-f]+/data/" + SOURCE_NAME.replace(".", r"\."),
            u.path,
        ))
    )


def _safe_cell(value: str) -> str:
    # Instrument names are untrusted text from a downloaded external file.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def parse_xetra(raw: bytes, metadata: dict, *, as_of: date):
    """Validate a manually acquired original file; emit only reference candidates."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Missing or oversized Xetra snapshot")
    if not isinstance(as_of, date) or not isinstance(metadata, dict):
        raise ValueError("Invalid Xetra metadata/as_of")
    digest = hashlib.sha256(raw).hexdigest()
    if (metadata.get("provider") != PROVIDER or
            metadata.get("sha256") != digest or
            not _official_url(metadata.get("source_url", ""))):
        raise ValueError("Source URL, provider or SHA-256 not verified")
    retrieved = _retrieved(metadata.get("retrieved_at_utc"))
    if retrieved.date() > as_of:
        raise ValueError("Xetra download is newer than research as_of")
    encoding = metadata.get("encoding", "utf-8-sig")
    if encoding not in ("utf-8-sig", "latin-1"):
        raise ValueError("Explicit supported source encoding required")
    try:
        content = raw.decode(encoding)
    except UnicodeError:
        raise ValueError("Undecodable Xetra CSV; do not guess encoding") from None
    lines = content.splitlines(keepends=True)
    if len(lines) < 4 or lines[0].strip() not in ("Market: XETR", "Market:;XETR"):
        raise ValueError("Not an XETR instrument reference file")
    header_date = re.fullmatch(
        r"Date Last Update:\s*;?\s*(\d{2}\.\d{2}\.\d{4})(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s*",
        lines[1].strip(),
    )
    if not header_date:
        raise ValueError("Missing official Xetra update date")
    try:
        updated = datetime.strptime(header_date.group(1), "%d.%m.%Y").date()
    except ValueError:
        raise ValueError("Invalid official Xetra update date") from None
    if updated > retrieved.date() or updated > as_of:
        raise ValueError("Xetra reference file date is in the future")
    reader = csv.DictReader(io.StringIO("".join(lines[2:])), delimiter=";", strict=True)
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)) or not REQUIRED.issubset(headers):
        raise ValueError("Unexpected Xetra T7 schema; no guessed column mapping")
    result, counts, skipped = [], Counter(), Counter()
    seen = set()
    for idx, row in enumerate(reader, start=1):
        if idx > MAX_ROWS:
            raise ValueError("Xetra candidate count exceeds limit")
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Malformed Xetra source row")
        if row["Product Status"] != "Active" or row["Instrument Status"] != "Active":
            skipped["NOT_ACTIVE"] += 1
            continue
        code = row["Instrument Type"].strip().upper()
        if code not in TYPES:
            skipped["UNKNOWN_INSTRUMENT_TYPE"] += 1
            continue
        isin = row["ISIN"].strip().upper()
        name = row["Instrument"].strip()
        symbol = row["Mnemonic"].strip()
        venue = row["MIC Code"].strip()
        currency = row["Settlement Currency"].strip()
        if (not valid_isin(isin) or not 0 < len(name) <= 300 or
                any(ord(ch) < 32 for ch in name) or
                not re.fullmatch(r"[A-Za-z0-9._-]{0,24}", symbol) or
                venue != "XETR" or
                not re.fullmatch(r"[A-Z]{3}", currency)):
            raise ValueError("Invalid Xetra identity or venue on active row")
        identity = (isin, symbol, currency, venue)
        if identity in seen:
            raise ValueError("Duplicated Xetra listing; manual review required")
        seen.add(identity)
        counts[code] += 1
        result.append({
            "isin": isin, "instrument": name, "mnemonic": symbol,
            "venue": venue, "currency": currency,
            "source_instrument_type": code, "asset_type": TYPES[code],
            "status": "DISCOVERY_ONLY_NO_PRICES_NO_TAX_OR_EXPOSURE_CERTIFICATION",
        })
    if not result:
        raise ValueError("No active Xetra instruments in snapshot")
    result.sort(key=lambda x: (x["asset_type"], x["isin"], x["mnemonic"], x["currency"]))
    manifest = {
        "schema_version": SCHEMA,
        "provider": PROVIDER, "source_url": metadata["source_url"],
        "as_of": as_of.isoformat(), "source_update_date": updated.isoformat(),
        "retrieved_at_utc": retrieved.isoformat(),
        "source_raw_sha256": digest, "source_encoding": encoding,
        "total_source_rows": sum(counts.values()) + sum(skipped.values()),
        "candidate_count": len(result),
        "source_type_counts": dict(sorted(counts.items())),
        "skipped_counts": dict(sorted(skipped.items())),
        "mode": "DISCOVERY_ONLY_UNRANKED_NO_PRICE_SCORE",
        "limitations": [
            "Actual Xetra reference identities only; not a global historic survivorship-free sample",
            "ETF does not establish UCITS tax classification and WAR does not establish certificate treatment",
            "Neither ETF/ETC/ETN underlying oil/gold exposure nor Euro Stoxx 50 overlap was checked",
            "No 61-session prices, adjustments, valuation, liquidity, spread, wallet or broker access",
            "Raw vendor data must not be committed, redistributed or processed outside permitted use",
        ],
    }
    return result, manifest


# Stable acquisition-only sample: does NOT select investment opportunities.
# A new daily snapshot can add/remove source rows, but existing ISIN ordering
# stays stable so that a 61-session data-provider pilot has fixed identities.
PROBE_QUOTAS = {"CS": 16, "ETF": 12, "ETC": 6, "ETN": 6}
PROBE_SEED = "decision-2026-xetra-price-source-coverage-v1"
VISIBLE_CONFLICT_TERMS = re.compile(
    r"\b(?:gold|oil|petroleum|crude|brent|wti|bitcoin|ethereum|crypto|"
    r"leverage|leveraged|short)\b", flags=re.IGNORECASE,
)


def select_xetra_price_coverage_probe(candidates: list, manifest: dict):
    """Unranked deterministic 0..40 source identities to CHECK provider coverage.

    WARNING: selection by SHA-256 is a reproducible stratified sample, not
    momentum/fundamental/quality analysis or suitability screening. The visible
    label filter only defers obvious conflicts; unlabelled indirect exposure,
    fund status, broker availability and tax remain UNKNOWN.
    """
    if (manifest.get("provider") != PROVIDER or
            manifest.get("mode") != "DISCOVERY_ONLY_UNRANKED_NO_PRICE_SCORE" or
            manifest.get("candidate_count") != len(candidates)):
        raise ValueError("Xetra probe requires a validated discovery manifest")
    groups = {key: [] for key in PROBE_QUOTAS}
    deferred = Counter()
    seen = set()
    for row in candidates:
        if not isinstance(row, dict) or row.get("status") != "DISCOVERY_ONLY_NO_PRICES_NO_TAX_OR_EXPOSURE_CERTIFICATION":
            raise ValueError("Unvalidated Xetra discovery row")
        code = row.get("source_instrument_type")
        isin = row.get("isin", "")
        if not isinstance(isin, str) or not valid_isin(isin):
            raise ValueError("Xetra probe requires an ISIN-checksummed identity")
        if isin in seen:
            # Same ISIN can have multiple listings; never double-count exposure.
            deferred["DUPLICATE_ISIN"] += 1
            continue
        seen.add(isin)
        if code not in groups:
            deferred["OUTSIDE_PROBE_ASSET_TYPES"] += 1
            continue
        if row.get("currency") != "EUR" or not row.get("mnemonic"):
            deferred["NON_EUR_OR_MISSING_SYMBOL"] += 1
            continue
        if VISIBLE_CONFLICT_TERMS.search(str(row.get("instrument", ""))):
            deferred["OBVIOUS_NAME_CONFLICT_REVIEW"] += 1
            continue
        groups[code].append(row)
    selected = []
    counts = {}
    for code, quota in PROBE_QUOTAS.items():
        pool = sorted(groups[code], key=lambda r: (
            hashlib.sha256(f"{PROBE_SEED}|{code}|{r['isin']}".encode("ascii")).hexdigest(),
            r["isin"],
        ))
        chosen = pool[:quota]
        selected.extend(chosen)
        counts[code] = {"quota": quota, "eligible_discovery_rows": len(pool),
                        "selected": len(chosen)}
    fingerprint = hashlib.sha256(
        json.dumps([{"type": r["source_instrument_type"], "isin": r["isin"]}
                    for r in selected], sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    audit = {
        "mode": "UNRANKED_COVERAGE_PROBE_NO_SECURITY_SELECTION",
        "selected_count": len(selected),
        "max_count": sum(PROBE_QUOTAS.values()),
        "by_type": counts,
        "source_raw_sha256": manifest["source_raw_sha256"],
        "cohort_identity_sha256": fingerprint,
        "deferred_counts": dict(sorted(deferred.items())),
        "method": "Deterministic stratified ISIN hash for price-provider coverage only",
        "next_gate": "61 licensed split-checked price sessions plus KID/prospectus, broker ISIN tax, gold/oil and factor review",
        "trade_ready": False,
        "research_screening_performed": False,
    }
    return selected, audit


def write_xetra_candidates(raw_path: Path, metadata_path: Path, as_of: date,
                           output: Path, *, repo_root: Path):
    """No download and no publication of actual-source reference data in Git."""
    root = Path(repo_root).resolve()
    out = Path(output).resolve()
    try:
        rel = out.relative_to(root)
    except ValueError:
        rel = None
    if rel is not None and rel.parts[:2] != ("data", "private"):
        raise ValueError("Xetra output inside repository must be under data/private/")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Xetra output already populated; no implicit overwrite")
    raw_path = Path(raw_path)
    if raw_path.stat().st_size > MAX_BYTES:
        raise ValueError("Oversized Xetra file")
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    candidates, manifest = parse_xetra(raw_path.read_bytes(), metadata, as_of=as_of)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in candidates:
        writer.writerow({k: _safe_cell(row[k]) for k in FIELDS})
    csv_bytes = stream.getvalue().encode("utf-8")
    manifest["candidate_csv_sha256"] = hashlib.sha256(csv_bytes).hexdigest()
    # A private 40-identity source-coverage sample is an acquisition input,
    # never a research score or investment recommendation.
    probe_rows, probe = select_xetra_price_coverage_probe(candidates, manifest)
    sample_stream = io.StringIO(newline="")
    sample_writer = csv.DictWriter(sample_stream, fieldnames=FIELDS, lineterminator="\\n")
    sample_writer.writeheader()
    for row in probe_rows:
        sample_writer.writerow({k: _safe_cell(row[k]) for k in FIELDS})
    probe_bytes = sample_stream.getvalue().encode("utf-8")
    probe["sample_csv_sha256"] = hashlib.sha256(probe_bytes).hexdigest()
    manifest["price_source_probe_selected_count"] = probe["selected_count"]
    manifest["price_source_probe_identity_sha256"] = probe["cohort_identity_sha256"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "XETRA_UNRANKED_CANDIDATES.csv").write_bytes(csv_bytes)
    (out / "XETRA_PRICE_SOURCE_PROBE_UNRANKED.csv").write_bytes(probe_bytes)
    (out / "XETRA_PRICE_SOURCE_PROBE_MANIFEST.json").write_text(
        json.dumps(probe, ensure_ascii=False, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )
    (out / "XETRA_DISCOVERY_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
