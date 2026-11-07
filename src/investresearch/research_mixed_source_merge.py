"""R-004/R-005/M3: local mixed US/Europe source manifest composer.

Combines separately acquired original Tiingo US and FWB Xetra private files.
No market feed, scraping, remote fetch, licence certification, implied foreign
exchange, paid subscription, issuer discovery, or fake ranking. All source
bytes, identities and documented use rights are checked BEFORE output write.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .quality import valid_isin
from .research_bundle import EXTERNAL
from .research_fwb_local import (
    PROVIDER as FWB, normalize_private_fwb,
)
from .research_tiingo_local import (
    PROVIDER as TIINGO, normalize_private_tiingo, MAX_BYTES as TIINGO_MAX,
)

VERSION = "r004-mixed-source-private-intake-v1"
MAX_SOURCES = 500
MAX_SPEC_BYTES = 100_000
MAX_FWB_BYTES = 5_000_000
MAX_TOTAL_SOURCE_BYTES = 150_000_000
ALLOWED_KINDS = frozenset((
    "EQUITY", "ETF_UCITS", "ETF_LEGAL_STATUS_UNVERIFIED",
    "ETC", "ETN", "CERTIFICATE", "BOND",
))
ALLOWED_OIL = frozenset(("none","indirect","material","primary","unknown"))


def _private(path, root):
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("Original private source path missing")
    raw = Path(path).expanduser()
    if raw.is_symlink():
        raise ValueError("Untrusted source symlinks are forbidden")
    resolved = raw.resolve()
    repo = Path(root).resolve()
    if resolved.is_relative_to(repo) and not resolved.is_relative_to(repo/"data/private"):
        raise ValueError("Original source files inside repository must stay in data/private")
    return resolved


def _file(path, cap):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original source must be a regular non-symlink file")
    if not 0 < path.stat().st_size <= cap:
        raise ValueError("Original source is missing/oversize")
    return path.read_bytes()


def _original(asset, as_of, *, root):
    if (not isinstance(asset, dict) or not isinstance(asset.get("id"),str)
            or not asset["id"].replace("-","").replace("_","").isalnum()
            or not isinstance(asset.get("name"),str) or not asset["name"].strip()
            or not valid_isin(asset.get("isin",""))
            or asset.get("asset_type") not in ALLOWED_KINDS
            or asset.get("oil_exposure") not in ALLOWED_OIL):
        raise ValueError("Original security identity/type/exposure is missing or invalid")
    src = asset.get("prices_source")
    if not isinstance(src,dict) or src.get("provider") not in (TIINGO, FWB):
        raise ValueError("Mixed intake accepts only Tiingo Personal or manual FWB original history")
    original_path = _private(src.get("path"),root)
    provider=src["provider"]
    raw=_file(original_path, TIINGO_MAX if provider==TIINGO else MAX_FWB_BYTES)
    sha=hashlib.sha256(raw).hexdigest()
    if src.get("sha256")!=sha:
        raise ValueError("Original vendor price bytes fail their SHA-256")
    if provider==TIINGO:
        if asset["asset_type"] not in ("EQUITY","ETF_LEGAL_STATUS_UNVERIFIED"):
            raise ValueError("Tiingo Personal asset type is not independently classified")
        normalized,info=normalize_private_tiingo(
            src,raw,as_of,asset,repo_root=root)
    else:
        if asset.get("asset_type")=="ETF_LEGAL_STATUS_UNVERIFIED":
            # A European ETF must have its legal/tax status reviewed
            # separately rather than inheriting a US source placeholder.
            raise ValueError("FWB asset legal type must be explicit")
        normalized,info=normalize_private_fwb(
            src,raw,as_of,asset,repo_root=root)
    if len(normalized)<61:
        raise ValueError("Mixed source has fewer than 61 original dated sessions")
    return {
        "provider":provider,
        "raw_sha256":sha,
        "source_sessions":len(normalized),
        "first_session":normalized[0]["date"],
        "last_session":normalized[-1]["date"],
        "price_basis":info["price_basis"],
        "corporate_actions_independently_verified":False,
        "license_independently_verified":False,
    }


def combine_mixed(*, source_specs, output, repo_root):
    """Create ONE original-source-referencing multi-asset spec, no FX and no network.

    Input: 2–500 existing one-security BUNDLE_INPUT_SPEC.json/hand-authored FWB
    files with matching as_of. Outputs only after full source preflight.
    """
    if (not isinstance(source_specs,list) or not 2<=len(source_specs)<=MAX_SOURCES):
        raise ValueError("Mixed US/EU intake requires 2–500 original source specs")
    root=Path(repo_root).resolve()
    out=_private(output,root)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Mixed output must be a NEW file in an existing private directory")
    seen_spec, seen_isin, seen_id, seen_raw, assets=set(),set(),set(),set(),[]
    audit=[]
    as_of=None
    total_bytes=0
    for raw_path in source_specs:
        spec_path=_private(raw_path,root)
        if spec_path in seen_spec:
            raise ValueError("Duplicate original source specification")
        seen_spec.add(spec_path)
        spec_raw=_file(spec_path,MAX_SPEC_BYTES)
        total_bytes+=len(spec_raw)
        try:
            spec=json.loads(spec_raw)
        except (UnicodeError,ValueError):
            raise ValueError("Original source spec JSON malformed") from None
        if (not isinstance(spec,dict)
                or set(spec)!={"mode","as_of","assets"}
                or spec.get("mode")!=EXTERNAL
                or not isinstance(spec.get("assets"),list)
                or len(spec["assets"])!=1):
            raise ValueError("Original input must contain exactly one external security and no FX/events")
        try:
            when=date.fromisoformat(spec["as_of"])
        except (TypeError,ValueError):
            raise ValueError("Original source as-of is missing/invalid") from None
        if when>date.today():
            raise ValueError("Cannot create a future-dated research universe")
        if as_of is None:
            as_of=when
        elif as_of!=when:
            raise ValueError("Mixed sources must have identical dated research cutoff")
        asset=spec["assets"][0]
        if not isinstance(asset,dict):
            raise ValueError("Malformed original instrument row")
        uid,isin=asset.get("id"),asset.get("isin")
        if uid in seen_id or isin in seen_isin:
            raise ValueError("Duplicate global ISIN or instrument ID across US/EU")
        source=asset.get("prices_source")
        if not isinstance(source,dict):
            raise ValueError("Original source metadata missing")
        orig=_original(asset,as_of,root=root)
        if orig["raw_sha256"] in seen_raw:
            raise ValueError("Repeated original market bytes; never count copied sources twice")
        seen_id.add(uid);seen_isin.add(isin);seen_raw.add(orig["raw_sha256"])
        total_bytes+= (Path(source["path"]).stat().st_size)
        if total_bytes>MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("Total approved private source volume too large")
        audit.append({
            "id_sha256":hashlib.sha256(uid.encode()).hexdigest(),
            "isin_sha256":hashlib.sha256(isin.encode()).hexdigest(),
            "original_spec_sha256":hashlib.sha256(spec_raw).hexdigest(),
            **orig,
        })
        assets.append(asset)
    merged={"mode":EXTERNAL,"as_of":as_of.isoformat(),
            "assets":sorted(assets,key=lambda r:(r["isin"],r["id"]))}
    # B's build_bundle reparses the original raw bytes; this stage never
    # grants provenance beyond operator-attested/noncommercial-only source terms.
    payload=json.dumps(merged,indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    out.write_text(payload,encoding="utf-8")
    return {
        "schema_version":VERSION,
        "as_of":as_of.isoformat(),
        "source_count":len(audit),
        "by_provider":dict(sorted(Counter(x["provider"] for x in audit).items())),
        "by_asset_type":dict(sorted(Counter(x["asset_type"] for x in assets).items())),
        "source_audits":audit,
        "merged_spec_sha256":hashlib.sha256(payload.encode()).hexdigest(),
        "fx_needed":any(x["currency"]=="USD" for x in assets),
        "fx_bound":False,
        "source_licences_independently_authenticated":False,
        "source_identities_independently_authenticated":False,
        "original_corporate_actions_independently_verified":False,
        "universe_representativeness_certified":False,
        "trade_ready":False,
        "next_step":"If USD exists, bind original official ECB FX; build the same source-bounded B bundle and run screen/funnel/private integration.",
    }
