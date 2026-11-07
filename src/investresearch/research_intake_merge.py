"""M3/M4: combine multiple separately acquired FREE Tiingo private source specs.

No network, account, new price history, model score or API key. This enables
the actual global R-007 *input preparation* without manually copying prices.
It is NOT evidence that 200+ symbols were sourced or legally eligible.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from .quality import valid_isin
from .research_bundle import EXTERNAL
from .research_tiingo_local import PROVIDER as TIINGO, ATTESTATION, MAPPING, VENUES

VERSION = "r004-free-tiingo-private-multiasset-merge-v1"
MAX_SOURCES = 500
MAX_SPEC_BYTES = 64_000
MAX_PRICE_BYTES = 250_000


def _private(path, repo_root):
    p = Path(path).expanduser().resolve()
    repo = Path(repo_root).resolve()
    if p.is_relative_to(repo) and not p.is_relative_to(repo/"data/private"):
        raise ValueError("Personal vendor inputs/output in repo must stay under data/private/")
    return p


def combine(*, source_specs: list[Path], output: Path, repo_root: Path):
    if not isinstance(source_specs,list) or not 2<=len(source_specs)<=MAX_SOURCES:
        raise ValueError("Combine between 2 and 500 independently acquired Tiingo sources")
    destination = _private(output, repo_root)
    if destination.exists():
        raise ValueError("Use NEW output spec, no overwriting prior source manifests")
    if not destination.parent.is_dir():
        raise ValueError("Create the private destination folder first")
    identities, symbols, raw_hashes, seen_files = set(), set(), set(), set()
    assets, original_specs = [], []
    as_of = None

    for source_file in source_specs:
        spec_file = _private(source_file, repo_root)
        if spec_file in seen_files or not spec_file.is_file():
            raise ValueError("Repeated or missing input source spec")
        seen_files.add(spec_file)
        if not 1<=spec_file.stat().st_size<=MAX_SPEC_BYTES:
            raise ValueError("Oversized source spec")
        raw_spec = spec_file.read_bytes()
        try:
            document = json.loads(raw_spec)
        except (ValueError,UnicodeError):
            raise ValueError("Malformed private intake spec JSON") from None
        if not isinstance(document,dict) or document.get("mode")!=EXTERNAL:
            raise ValueError("Refusing a synthetic or unidentified source spec")
        if document.get("fx_source") is not None or document.get("events_source") is not None:
            raise ValueError("Bind FX/events ONCE after merging, not separately per instrument")
        rows = document.get("assets")
        if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
            raise ValueError("Source intake must describe exactly one verified security")
        try:
            current_date = date.fromisoformat(document["as_of"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Missing source trading as-of date") from None
        if current_date.year!=2026:
            raise ValueError("Expected 2026 point-in-time source date")
        if as_of is None:
            as_of=current_date
        elif as_of!=current_date:
            raise ValueError("Cannot merge asynchronous source as-of dates")

        asset = rows[0]
        isin, symbol_source = asset.get("isin"), asset.get("prices_source")
        if not isinstance(symbol_source,dict) or symbol_source.get("provider")!=TIINGO:
            raise ValueError("No EODHD, unknown feed or synthetic provider in free Tiingo merge")
        if (not valid_isin(isin) or asset.get("id")!=isin
                or asset.get("venue") not in VENUES
                or asset.get("currency")!="USD"
                or asset.get("asset_type") not in ("EQUITY","ETF_LEGAL_STATUS_UNVERIFIED")
                or not isinstance(asset.get("sector"),str) or not asset["sector"].strip()
                or asset.get("oil_exposure") not in ("none","indirect","material","primary","unknown")
                or symbol_source.get("usage_attestation")!=ATTESTATION
                or symbol_source.get("identity_evidence_status")!=MAPPING
                or any(symbol_source.get(k)!=asset.get(k) for k in ("isin","venue","currency"))):
            raise ValueError("Incomplete explicit ISIN/venue/type/rights input; not verified")
        symbol = symbol_source.get("symbol")
        if not isinstance(symbol,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,29}",symbol):
            raise ValueError("Malformed Tiingo source symbol")
        if isin in identities or symbol.upper() in symbols:
            raise ValueError("Duplicate symbol or ISIN between independently acquired inputs")
        identities.add(isin); symbols.add(symbol.upper())
        if symbol_source.get("source_url")!=f"https://api.tiingo.com/tiingo/daily/{symbol}/prices":
            raise ValueError("Official Tiingo token-free source URL mismatch")
        source_raw = _private(symbol_source.get("path",""),repo_root)
        if not source_raw.is_file() or not 0<source_raw.stat().st_size<=MAX_PRICE_BYTES:
            raise ValueError("Missing/oversized original Tiingo EOD snapshot")
        digest = hashlib.sha256(source_raw.read_bytes()).hexdigest()
        if symbol_source.get("sha256")!=digest or digest in raw_hashes:
            raise ValueError("Price SHA mismatch or duplicate raw payload")
        raw_hashes.add(digest)
        source_stamp = symbol_source.get("retrieved_at_utc")
        try:
            dt = datetime.fromisoformat(source_stamp.replace("Z","+00:00"))
        except (TypeError,AttributeError,ValueError):
            raise ValueError("Missing/invalid source acquisition time") from None
        if dt.tzinfo is None or dt.utcoffset()!=timedelta(0) or dt.date()>as_of:
            raise ValueError("Source acquisition date/UTC timing inconsistent with research cutoff")
        assets.append(asset)
        original_specs.append({
            "source_spec_sha256":hashlib.sha256(raw_spec).hexdigest(),
            "isin_sha256":hashlib.sha256(isin.encode()).hexdigest(),
            "provider":"TIINGO_EOD_PERSONAL_RESEARCH",
        })

    merged={"mode":EXTERNAL,"as_of":as_of.isoformat(),
            "assets":sorted(assets,key=lambda r:r["isin"])}
    # Explicitly no FX; the official ECB binder is the only supported
    # next step. This prevents a false cross-currency ranked report.
    destination.write_text(json.dumps(merged,indent=2,sort_keys=True,
                                     ensure_ascii=False)+"\n",encoding="utf-8")
    return {
        "schema_version":VERSION,
        "as_of":as_of.isoformat(),
        "source_assets":len(assets),
        "by_type":dict(sorted(Counter(x["asset_type"] for x in assets).items())),
        "original_source_hashes":original_specs,
        "output_sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),
        "fx_bound":False,
        "next_gate":"Bind original official ECB EUR/USD source before building",
        "licences_independently_authenticated":False,
        "actual_prices_quality_tested":False,
        "trade_ready":False,
    }
