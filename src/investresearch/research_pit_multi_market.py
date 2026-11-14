"""P0 offline historical multi-market PIT *candidate* sampling, not a backtest.

Only original operator-supplied, SHA-256-bound dated membership snapshots are
read. No network access, price downloads, performance inspection, provider
right certification, historical cashflow imputation, trading or paid services.

A 2026 transcription of a 2021 archive remains operator-asserted evidence:
a dated document and an ISIN alone do NOT certify point-in-time truth.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re

from .quality import valid_isin
from .research_historical_validation_v2 import preregistered_anchors
from .research_historical_validation_v3 import v3_protocol

SCHEMA = "R004_MULTI_MARKET_PIT_CANDIDATE_PACK_V1"
RESULT = "R004_MULTI_MARKET_PIT_PILOT_AUDIT_V1"
VENUES = {"USA": frozenset(("XNYS", "XNAS")),
          "ITALY": frozenset(("XMIL",)),
          "GERMANY": frozenset(("XETR",)),
          "FRANCE": frozenset(("XPAR",))}
FIELDS = ("security_key", "isin", "venue", "sector", "asset_type",
          "oil_exposure", "listing_date")
SOURCE_KINDS = frozenset(("OFFICIAL_HISTORICAL_SNAPSHOT_OPERATOR_TRANSCRIBED",
                          "ARCHIVED_HISTORICAL_SNAPSHOT_OPERATOR_TRANSCRIBED"))
RIGHTS = frozenset(("OPERATOR_REVIEWED_PERSONAL_NONCOMMERCIAL",
                    "UNVERIFIED", "RESTRICTED", "REQUIRES_PERMISSION"))
SHA = re.compile(r"[0-9a-f]{64}\Z")
KEY = re.compile(r"[A-Za-z0-9_-]{3,90}\Z")
MAX_SNAPSHOTS = 240
MAX_ROWS = 20000
MAX_SOURCE_BYTES = 2_000_000
MAX_PACK_BYTES = 180_000


def _private_file(path, private_root: Path):
    root = Path(private_root).absolute()
    candidate = Path(path).absolute()
    if (root.is_symlink() or candidate.is_symlink()
            or not candidate.is_relative_to(root)
            or not root.is_dir() or not candidate.is_file()):
        raise ValueError("Only original regular files inside the private intake directory")
    # Reject symlink traversal in every relative ancestor, including the root.
    if root.resolve() != root or candidate.resolve() != candidate:
        raise ValueError("Private original source path contains a symlink")
    if not 0 < candidate.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Missing or oversized original membership input")
    return candidate


def _bytes(path, expected, private_root):
    if not isinstance(expected, str) or SHA.fullmatch(expected) is None:
        raise ValueError("Original source requires full SHA-256")
    raw = _private_file(path, private_root).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Original membership source SHA-256 mismatch")
    return raw


def _iso(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Exact ISO snapshot date is required")
    return date.fromisoformat(value)


def _source_url(s):
    if (not isinstance(s, str) or not s.startswith("https://")
            or len(s) > 1500 or "@" in s.split("/")[2]
            or "#" in s or "?" in s.split("/")[2]):
        raise ValueError("Original historical source URL requires plain HTTPS")


def _roster(raw, venue_group, snapshot_day):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeError as exc:
        raise ValueError("Roster must be UTF-8") from exc
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError("Original PIT transcribed roster schema drift")
    result = []
    seen_keys, seen_listings = set(), set()
    for row in reader:
        if len(result) >= MAX_ROWS or None in row or any(v is None for v in row.values()):
            raise ValueError("Malformed or oversized PIT roster")
        sid = row["security_key"]
        listed = row["listing_date"]
        if (not KEY.fullmatch(sid) or not valid_isin(row["isin"])
                or row["venue"] not in VENUES[venue_group]
                or row["asset_type"] != "EQUITY"
                or not row["sector"] or len(row["sector"]) > 80
                or row["oil_exposure"] not in ("none", "indirect", "material",
                                               "primary", "unknown")):
            raise ValueError("Malformed security identity, venue or exposure")
        if (sid in seen_keys or (row["isin"], row["venue"]) in seen_listings):
            raise ValueError("Duplicate historical security or listing identity")
        if not listed or _iso(listed) > snapshot_day:
            raise ValueError("Original source has future or missing listing start")
        seen_keys.add(sid)
        seen_listings.add((row["isin"], row["venue"]))
        result.append(row)
    if not result:
        raise ValueError("Historical source roster is empty")
    return result


def read_historical_pack(pack_path: Path, *, private_root: Path):
    pack_file = _private_file(pack_path, private_root)
    raw = pack_file.read_bytes()
    if len(raw) > MAX_PACK_BYTES:
        raise ValueError("Unbounded original PIT source pack")
    try:
        pack = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid PIT source pack JSON") from exc
    if (not isinstance(pack, dict) or
            set(pack) != {"schema_version", "snapshots"} or
            pack.get("schema_version") != SCHEMA or
            not isinstance(pack.get("snapshots"), list) or
            not 1 <= len(pack["snapshots"]) <= MAX_SNAPSHOTS):
        raise ValueError("Unrecognized original PIT source pack")
    snapshots = {}
    for spec in pack["snapshots"]:
        needed = {"market", "snapshot_as_of", "original_published_on", "original_effective_on",
                  "source_kind", "usage_rights",
                  "source_url", "original_path", "original_sha256",
                  "transcription_path", "transcription_sha256"}
        if not isinstance(spec, dict) or set(spec) != needed:
            raise ValueError("PIT snapshot requires exact evidence fields")
        market = spec["market"]
        if market not in VENUES or spec["source_kind"] not in SOURCE_KINDS:
            raise ValueError("PIT market or membership source kind not supported")
        day = _iso(spec["snapshot_as_of"])
        published = _iso(spec["original_published_on"])
        effective = _iso(spec["original_effective_on"])
        if published > day or effective > day or effective < published:
            raise ValueError("Historical membership announcement is not effective at the claimed snapshot")
        if spec["usage_rights"] not in RIGHTS:
            raise ValueError("Original source usage permission not classified")
        _source_url(spec["source_url"])
        original = _bytes(spec["original_path"], spec["original_sha256"], private_root)
        rows_raw = _bytes(spec["transcription_path"], spec["transcription_sha256"], private_root)
        if hashlib.sha256(original).hexdigest() == hashlib.sha256(rows_raw).hexdigest():
            raise ValueError("Original document and reviewed transcription must be separate")
        rows = _roster(rows_raw, market, day)
        group = snapshots.setdefault(market, {})
        if spec["snapshot_as_of"] in group:
            raise ValueError("Duplicate historical snapshot date for market")
        group[spec["snapshot_as_of"]] = (spec, rows)
    return raw, snapshots


def _draw(rows, anchor, market, seed, *, quota, cap_per_sector):
    """No price/outcome input; deterministic per-anchor pre-outcome lottery."""
    eligible = []
    counts = Counter()
    for r in rows:
        if r["listing_date"] > anchor:
            continue
        if r["oil_exposure"] != "none":
            counts["excluded_oil_or_unverified_exposure"] += 1
            continue
        eligible.append(r)
    # Separate sectors first, then deterministic within-sector, all pre-outcome.
    by_sector = {}
    for r in eligible:
        by_sector.setdefault(r["sector"], []).append(r)
    for sector in by_sector:
        by_sector[sector].sort(key=lambda r: (
            hashlib.sha256(f"{seed}|{anchor}|{market}|{r['security_key']}".encode()).hexdigest(),
            r["security_key"],
        ))
    # Interleave independent sectors to avoid concentrating the 8-name pilot.
    sectors = sorted(by_sector, key=lambda sec: (
        hashlib.sha256(f"{seed}|{anchor}|{market}|SECTOR|{sec}".encode()).hexdigest(), sec))
    chosen = []
    for i in range(cap_per_sector):
        for sector in sectors:
            if len(chosen) == quota:
                break
            if i < len(by_sector[sector]):
                chosen.append(by_sector[sector][i])
        if len(chosen) == quota:
            break
    counts["pre_outcome_eligible"] = len(eligible)
    counts["picked"] = len(chosen)
    return chosen, dict(counts)


def pilot_pit_multi_market(pack_path: Path, *, private_root: Path,
                           seed: str, first_anchors: int = 12,
                           quota_per_market: int = 8,
                           cap_per_sector: int = 3,
                           max_snapshot_age_days: int = 100) -> dict:
    if (not isinstance(seed, str) or SHA.fullmatch(seed) is None
            or type(first_anchors) is not int or not 1 <= first_anchors <= 37
            or type(quota_per_market) is not int or not 1 <= quota_per_market <= 24
            or type(cap_per_sector) is not int or not 1 <= cap_per_sector <= quota_per_market
            or type(max_snapshot_age_days) is not int or not 1 <= max_snapshot_age_days <= 120):
        raise ValueError("PIT diagnostic sampling controls are not bounded and explicit")
    raw, sources = read_historical_pack(pack_path, private_root=private_root)
    policy, v3hash = v3_protocol()
    # Exact V3 calendar; no moving decision dates after seeing returns.
    anchors = preregistered_anchors(["XNYS","XNAS","XMIL","XPAR","XETR"], policy)
    if first_anchors > len(anchors):
        raise ValueError("Original frozen V3 schedule has insufficient anchors")
    audits, accepted = [], 0
    for anchor in anchors[:first_anchors]:
        all_selected = []
        areas = {}
        for market in ("USA","ITALY","GERMANY","FRANCE"):
            candidates = [s for s in sources.get(market, {}) if s <= anchor]
            if not candidates:
                areas[market] = {"status":"BLOCKED_NO_HISTORICAL_MEMBERSHIP",
                                 "count":0}
                continue
            snapshot = max(candidates)
            spec, rows = sources[market][snapshot]
            age = (_iso(anchor) - _iso(snapshot)).days
            if age > max_snapshot_age_days:
                areas[market] = {"status":"BLOCKED_STALE_HISTORICAL_MEMBERSHIP",
                                 "count":0,"snapshot_as_of":snapshot,
                                 "age_days":age}
                continue
            if spec["usage_rights"] != "OPERATOR_REVIEWED_PERSONAL_NONCOMMERCIAL":
                areas[market] = {"status":"BLOCKED_SOURCE_USAGE_RIGHTS",
                                 "count":0,"snapshot_as_of":snapshot}
                continue
            chosen, counts = _draw(rows, anchor, market, seed,
                                   quota=quota_per_market,
                                   cap_per_sector=cap_per_sector)
            # Never fill a shortage with a later snapshot or with a
            # security chosen after looking at future returns.
            full = len(chosen) == quota_per_market
            areas[market] = {
                "status": "CANDIDATES_OPERATOR_ASSERTED_NOT_PIT_CERTIFIED" if full
                          else "BLOCKED_INSUFFICIENT_DIVERSE_CANDIDATES",
                "snapshot_as_of": snapshot, "source_original_sha256": spec["original_sha256"],
                "source_transcription_sha256": spec["transcription_sha256"],
                "source_usage_rights_operator_reviewed_not_authenticated": True,
                "count": len(chosen), "pre_outcome_counts": counts,
                "selected": [{"security_key":r["security_key"], "isin":r["isin"],
                              "venue":r["venue"], "sector":r["sector"]} for r in chosen],
            }
            all_selected.extend(chosen)
        full = all(areas[a]["status"] == "CANDIDATES_OPERATOR_ASSERTED_NOT_PIT_CERTIFIED"
                   for a in VENUES)
        # A duplicate global issuer / listing identifier is an identity
        # problem, not a reason to draw a replacement after the fact.
        ids = [x["security_key"] for x in all_selected]
        isins = [x["isin"] for x in all_selected]
        if len(ids) != len(set(ids)) or len(isins) != len(set(isins)):
            full = False
            areas["_identity"] = {"status":"BLOCKED_DUPLICATED_CROSS_MARKET_IDENTITY"}
        accepted += int(full)
        audits.append({
            "anchor":anchor,
            "status":("PILOT_COHORT_DRAWN_UNVERIFIED" if full
                      else "BLOCKED_INCOMPLETE_COHORT"),
            "picked":len(all_selected),
            "qualified_for_return_testing":False,
            "market":areas,
        })
    return {
        "schema_version":RESULT,
        "scope":"OFFLINE_MEMBERSHIP_DIAGNOSTIC_ONLY_NO_PRICE_DATA_OR_BACKTEST",
        "original_pack_sha256":hashlib.sha256(raw).hexdigest(),
        "v3_protocol_sha256":v3hash,
        "seed_sha256_predeclared_operator_value":seed,
        "pilot_anchors":len(audits),
        "quota_per_market":quota_per_market,
        "target_securities_per_anchor":quota_per_market * len(VENUES),
        "drawn_complete_unverified_anchors":accepted,
        "source_snapshot_count_by_market":{m:len(sources.get(m,{})) for m in VENUES},
        "anchor_audit":audits,
        "source_licence_independently_authenticated":False,
        "historical_membership_independently_authenticated":False,
        "source_transcriptions_independently_reconciled":False,
        "historic_security_issuer_continuity_verified":False,
        "prices_or_corporate_actions_acquired":False,
        "statistical_research_outcome_computed":False,
        "retrospective_run_is_independent_holdout":False,
        "research_ready":False,
        "predictive_edge_certified":False,
        "trade_ready":False,
    }


def write_private_pit_audit(report: dict, output_path: Path, *, private_root: Path) -> Path:
    root = Path(private_root).absolute()
    p = Path(output_path).absolute()
    if (root.is_symlink() or root.resolve() != root or
            not p.is_relative_to(root) or p.resolve() != p or p.is_symlink()
            or p.exists() or not p.parent.is_dir()):
        raise ValueError("PIT audit must be a NEW non-symlink file inside existing private root")
    body = json.dumps(report,sort_keys=True,indent=2,ensure_ascii=True) + "\n"
    with p.open("x",encoding="utf-8") as f:
        f.write(body)
    return p
