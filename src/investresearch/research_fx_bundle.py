"""R-005: safely attach official ECB EUR/USD source evidence to a US price spec.

No network, no paid API, no EODHD, no imagined FX. The normal build_bundle
still performs original SHA checks and point-in-time source parsing. An
acquisition timestamp proves collection order, NOT quote publication rights.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .research_sources import ECB_URL, ECB_CSV_URL, MAX_BYTES, parse_ecb
from .research_bundle import EXTERNAL

VERSION = "r005-ecb-fx-source-binding-v1"


def _as_utc(value):
    if not isinstance(value, str):
        raise ValueError("ECB acquisition timestamp missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid ECB acquisition timestamp") from None
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("ECB acquisition requires exact UTC timezone")
    return stamp


def _private(path, root):
    p=Path(path).expanduser().resolve()
    r=Path(root).resolve()
    if p.is_relative_to(r) and not p.is_relative_to(r/"data/private"):
        raise ValueError("External research source/output inside repo must be in data/private")
    return p


def bind_ecb_fx(*, spec_path: Path, fx_meta_path: Path, output: Path, repo_root: Path):
    """Return evidence summary; one new spec, original raw sources unchanged."""
    source=_private(spec_path,repo_root)
    meta_file=_private(fx_meta_path,repo_root)
    dest=_private(output,repo_root)
    if dest.exists() or dest==source or dest==meta_file:
        raise ValueError("ECB binding requires a new private output, never overwrite inputs")
    try:
        spec=json.loads(source.read_text(encoding="utf-8"))
        fxmeta=json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("Malformed/missing source spec or ECB metadata") from None
    if not isinstance(spec,dict) or spec.get("mode")!=EXTERNAL:
        raise ValueError("ECB binding requires external as-of research source spec")
    try:
        as_of=date.fromisoformat(spec["as_of"])
    except (KeyError,TypeError,ValueError):
        raise ValueError("Invalid original research as-of") from None
    assets=spec.get("assets")
    if not isinstance(assets,list) or not 1<=len(assets)<=5000:
        raise ValueError("Invalid nonempty research source list")
    if not any(isinstance(a,dict) and a.get("currency")=="USD" for a in assets):
        raise ValueError("ECB USD fixing only needed for EUR-converted USD assets")
    if "fx_source" in spec or fxmeta.get("provider")!="ECB_EUR_FX":
        raise ValueError("ECB FX source is already set or not official")
    if fxmeta.get("source_url") not in (ECB_URL, ECB_CSV_URL):
        raise ValueError("ECB source URL not official documented XML/CSV")
    rawpath=_private(fxmeta.get("path", ""),repo_root)
    if not rawpath.is_file() or not 0<rawpath.stat().st_size<=MAX_BYTES:
        raise ValueError("ECB raw source is missing or oversized")
    if not isinstance(fxmeta.get("sha256"),str) or not re.fullmatch(r"[0-9a-f]{64}",fxmeta["sha256"]):
        raise ValueError("ECB source SHA-256 must be declared")
    raw=rawpath.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=fxmeta["sha256"]:
        raise ValueError("ECB FX source SHA-256 mismatch")
    retrieved=_as_utc(fxmeta.get("retrieved_at_utc"))
    if retrieved.date()>as_of:
        raise ValueError("ECB FX collected after specified as-of; cannot backdate sources")
    rates=parse_ecb(raw,as_of)
    # A source collected on a given UTC day cannot contain future ECB fixings.
    # SHA-256 only confirms byte integrity, not point-in-time availability.
    if date.fromisoformat(rates[-1]["date"]) > retrieved.date():
        raise ValueError("ECB source contains fixing later than declared acquisition date")
    if rates[-1]["date"]< (as_of-timedelta(days=10)).isoformat():
        raise ValueError("ECB historic source stale at requested as-of")
    out=dict(spec)
    out["fx_source"]={
        "provider":"ECB_EUR_FX",
        "source_url":fxmeta["source_url"],
        "sha256":fxmeta["sha256"],
        "path":str(rawpath),
        "retrieved_at_utc":retrieved.isoformat(),
    }
    if not dest.parent.is_dir():
        raise ValueError("Create new private output folder before writing ECB-bound spec")
    dest.write_text(json.dumps(out,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    return {
        "schema_version":VERSION,
        "mode":EXTERNAL,
        "as_of":as_of.isoformat(),
        "assets_total":len(assets),
        "usd_assets":sum(isinstance(a,dict) and a.get("currency")=="USD" for a in assets),
        "ecb_dates_available":len(rates),
        "first_ecb_date":rates[0]["date"],
        "last_ecb_date":rates[-1]["date"],
        "source_sha256":fxmeta["sha256"],
        "status":"OFFLINE_OFFICIAL_ECB_SOURCE_BOUND_NEEDS_BUILD_AND_SESSION_ALIGNMENT",
        "fee_or_subscription_required":False,
        "trade_ready":False,
    }
