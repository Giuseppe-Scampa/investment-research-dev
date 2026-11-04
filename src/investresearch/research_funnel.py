"""R-006/R-007/R-008 (M4): reproducible evidence-gated candidate funnel.

This is research triage, not a performance model, a real-world universe,
a trade signal, or a substitute for independently verified price data.
No source material or broker data leaves the local computer.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin
from .research_bundle import SYNTHETIC

VERSION = "r007-research-funnel-v1"
DILIGENCE_VERSION = "r007-manual-diligence-v1"
MAX_UNIVERSE = 5000
SHA256 = re.compile(r"^[a-f0-9]{64}$")
ALLOWED_STATUS = {"DEMO_RANK_NOT_REAL_MARKET", "RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY"}
SYNTHETIC_STATUS = "DEMO_RANK_NOT_REAL_MARKET"
EXTERNAL_STATUS = "RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY"
ALLOWED_REVIEW = "RESEARCH_REVIEWED_NOT_TRADE_READY"
DEFAULT_POLICY = {
    "min_universe": 200, "min_ranked": 100,
    "research_pool": 40, "deep_dive": 6, "finalists": 3,
    "max_pool_per_sector": 10, "max_deep_dive_per_sector": 2,
}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _iso(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name}: ISO date required")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name}: ISO date required") from None


def _policy(raw):
    if raw is None:
        return dict(DEFAULT_POLICY)
    if not isinstance(raw, dict) or set(raw) != set(DEFAULT_POLICY):
        raise ValueError("Funnel policy requires exactly the documented fields")
    if any(type(v) is not int for v in raw.values()):
        raise ValueError("Funnel policy must contain positive integer values")
    p = dict(raw)
    if not (200 <= p["min_universe"] <= MAX_UNIVERSE
            and 100 <= p["min_ranked"] <= p["min_universe"]
            and 30 <= p["research_pool"] <= 60
            and 5 <= p["deep_dive"] <= 7
            and 1 <= p["finalists"] <= 3
            and p["finalists"] <= p["deep_dive"] <= p["research_pool"]
            and 1 <= p["max_pool_per_sector"] <= p["research_pool"]
            and 1 <= p["max_deep_dive_per_sector"] <= p["deep_dive"]):
        raise ValueError("Funnel limits must respect V3.0.0 R-007 stages")
    return p


def _source_url(value):
    if not isinstance(value, str) or len(value) > 1500:
        return False
    parts = urlsplit(value)
    return bool(parts.scheme == "https" and parts.hostname
                and not parts.username and not parts.password and not parts.fragment
                and parts.hostname.lower() not in {"localhost", "127.0.0.1", "::1"})


def _eligible(row, dataset_mode):
    failures = []
    if row.get("blocking_constraints"):
        failures.append("HARD_CONSTRAINT")
    if row.get("status") not in ALLOWED_STATUS:
        failures.append("NO_VALID_MARKET_RESEARCH_SCORE")
    if dataset_mode == SYNTHETIC and row.get("status") != SYNTHETIC_STATUS:
        failures.append("DATASET_STATUS_MISMATCH")
    if dataset_mode != SYNTHETIC and row.get("status") != EXTERNAL_STATUS:
        failures.append("DATASET_STATUS_MISMATCH")
    score = row.get("market_score")
    if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 100:
        failures.append("MISSING_OR_INVALID_SCORE")
    if row.get("trade_ready") is not False:
        failures.append("INVALID_TRADE_READY_CLAIM")
    if not isinstance(row.get("sector"), str) or not row.get("sector", "").strip():
        failures.append("UNKNOWN_SECTOR")
    if not isinstance(row.get("price_sha256"), str) or not SHA256.fullmatch(row["price_sha256"]):
        failures.append("MISSING_PRICE_CHECKSUM")
    if row.get("history_quality", {}).get("verified") is not True:
        failures.append("UNVERIFIED_61_SESSION_HISTORY")
    if dataset_mode != SYNTHETIC:
        if not valid_isin(row.get("isin", "")):
            failures.append("UNVERIFIED_ISIN")
        if not _source_url(row.get("price_source_url")):
            failures.append("UNVERIFIED_PRICE_SOURCE")
        if not row.get("venue") or not row.get("currency"):
            failures.append("INCOMPLETE_MARKET_IDENTITY")
    return sorted(set(failures))


def _diversified_pick(rows, n, per_sector):
    picked = []
    counts = Counter()
    for row in rows:
        key = row["sector"].strip().casefold()
        if counts[key] >= per_sector:
            continue
        picked.append(row)
        counts[key] += 1
        if len(picked) == n:
            break
    return picked


def _reviewed(diligence, as_of, manifest_sha, deep_dive):
    if diligence is None:
        return {}, "NO_MANUAL_DILIGENCE"
    if not isinstance(diligence, dict) or set(diligence) != {
            "schema_version", "as_of", "dataset_manifest_sha256", "reviews"}:
        raise ValueError("Diligence must use the exact approved schema")
    if diligence["schema_version"] != DILIGENCE_VERSION:
        raise ValueError("Unsupported diligence schema")
    if _iso(diligence["as_of"], "diligence.as_of") != as_of:
        raise ValueError("Diligence as_of does not match screening")
    if diligence["dataset_manifest_sha256"] != manifest_sha:
        raise ValueError("Diligence refers to a different research bundle")
    rows = diligence["reviews"]
    if not isinstance(rows, list) or len(rows) > len(deep_dive):
        raise ValueError("Diligence has an invalid count")
    allowed = {r["id"] for r in deep_dive}
    indexed = {}
    for entry in rows:
        keys = {"id", "status", "as_of", "upside_case", "downside_case",
                "counter_thesis", "valuation_limitations", "source_evidence"}
        if not isinstance(entry, dict) or set(entry) != keys:
            raise ValueError("Diligence review has missing or extra keys")
        uid = entry["id"]
        if not isinstance(uid, str) or uid not in allowed or uid in indexed:
            raise ValueError("Diligence references unselected or duplicate candidate")
        if entry["status"] != ALLOWED_REVIEW:
            raise ValueError("Diligence does not certify trade readiness")
        if _iso(entry["as_of"], "review.as_of") > as_of:
            raise ValueError("Diligence review occurs after research as_of")
        for key in ("upside_case", "downside_case", "counter_thesis", "valuation_limitations"):
            value = entry[key]
            if not isinstance(value, str) or not 8 <= len(value.strip()) <= 1000:
                raise ValueError("Diligence requires bounded substantive cases and limitations")
        evidence = entry["source_evidence"]
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
            raise ValueError("Review requires one to eight documented source references")
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {
                    "source_url", "published_date", "sha256"}:
                raise ValueError("Invalid evidence reference shape")
            if not _source_url(item["source_url"]):
                raise ValueError("Evidence source must have a public HTTPS URL")
            if _iso(item["published_date"], "evidence.published_date") > as_of:
                raise ValueError("Evidence was not published by research as_of")
            if item["sha256"] is not None and (
                    not isinstance(item["sha256"], str) or
                    not SHA256.fullmatch(item["sha256"])):
                raise ValueError("Evidence SHA256 must be valid or explicitly unknown")
        indexed[uid] = entry
    return indexed, "MANUAL_ASSERTIONS_NOT_INDEPENDENTLY_AUTHENTICATED"


def build_funnel(screening, *, policy=None, diligence=None):
    """Produce an auditable selection *queue*; never infer buy suitability."""
    p = _policy(policy)
    if not isinstance(screening, dict) or screening.get("schema_version") != 1:
        raise ValueError("Expected Block B screening schema v1")
    mode = screening.get("dataset_mode")
    if mode not in (SYNTHETIC, "EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE"):
        raise ValueError("Unknown dataset mode")
    as_of = _iso(screening.get("as_of"), "screening.as_of")
    rows = screening.get("results")
    sha = screening.get("dataset_manifest_sha256")
    if not isinstance(rows, list) or len(rows) > MAX_UNIVERSE:
        raise ValueError("Invalid screening universe size")
    if not isinstance(sha, str) or not SHA256.fullmatch(sha):
        raise ValueError("Missing bundle checksum")
    if screening.get("universe_size") != len(rows):
        raise ValueError("Screening universe count is inconsistent")
    seen = set()
    accepted, excluded = [], []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Malformed screening candidate")
        if row["id"] in seen:
            raise ValueError("Duplicate candidate ID")
        seen.add(row["id"])
        issues = _eligible(row, mode)
        if issues:
            excluded.append({"id": row["id"], "reasons": issues})
        else:
            accepted.append(row)
    accepted.sort(key=lambda x: (-x["market_score"], x["id"]))
    enough = len(rows) >= p["min_universe"] and len(accepted) >= p["min_ranked"]
    pool = (_diversified_pick(accepted, p["research_pool"],
                              p["max_pool_per_sector"]) if enough else [])
    deep = (_diversified_pick(pool, p["deep_dive"],
                              p["max_deep_dive_per_sector"]) if
            len(pool) >= p["research_pool"] else [])
    reviews, review_status = _reviewed(diligence, as_of, sha, deep)
    finalists = [r for r in deep if r["id"] in reviews][:p["finalists"]]
    def entry(row, stage):
        return {
            "id": row["id"], "name": row["name"], "isin": row.get("isin", ""),
            "sector": row["sector"], "venue": row["venue"],
            "market_score": row["market_score"], "stage": stage,
            "price_session": row["last_price_session"],
            "price_sha256": row["price_sha256"],
            "price_source_url": row.get("price_source_url", ""),
            "quality_status": row["status"],
            "warnings": row["warnings"],
            "trade_ready": False,
            "reason": ("Historical research rank with explicit sector diversity; "
                       "not an expected-return or valuation forecast"),
        }
    if not enough:
        status = "INSUFFICIENT_RESEARCH_UNIVERSE_NO_SHORTLIST"
    elif len(pool) < p["research_pool"]:
        status = "INSUFFICIENT_SECTOR_COVERAGE_NO_DEEP_DIVE"
    elif len(deep) < p["deep_dive"]:
        status = "INSUFFICIENT_REVIEW_DIVERSITY_NO_FINALISTS"
    elif not finalists:
        status = "AWAITING_INDEPENDENT_DILIGENCE_NO_FINALISTS"
    else:
        status = "PROVISIONAL_RESEARCH_FINALISTS_NOT_TRADE_READY"
    return {
        "schema_version": VERSION, "as_of": as_of.isoformat(),
        "dataset_mode": mode, "dataset_manifest_sha256": sha,
        "screening_sha256": hashlib.sha256(_canonical(screening)).hexdigest(),
        "policy": p, "status": status, "trade_ready": False,
        "input_universe_count": len(rows), "research_eligible_count": len(accepted),
        "excluded_count": len(excluded), "exclusion_reasons": excluded,
        "stage_1_pool": [entry(r, "RESEARCH_POOL") for r in pool],
        "stage_2_deep_dive": [entry(r, "NEEDS_DILIGENCE") for r in deep],
        "stage_3_provisional_finalists": [
            {**entry(r, "MANUAL_REVIEWED_PROVISIONAL"),
             "diligence": reviews[r["id"]]} for r in finalists],
        "manual_diligence_status": review_status,
        "limitations": [
            "This is a deterministic research triage, NOT global real-world coverage unless source universe proves it.",
            "No fake quota filling: incomplete sectors/sessions/sources produce no final shortlist.",
            "Scores are historical heuristics, not future returns or valuation.",
            "Manual reviews are supplied assertions; citations and arguments not independently fact-checked.",
            "Provisional research finalists are NOT broker-verified or trade-ready.",
            "Fiscal loss carryforward, broker account balances, fees and execution do not enter the public funnel.",
        ],
    }


def write_funnel(result, outdir, *, repo_root):
    """Public demo can write generated output; external research stays private."""
    out = Path(outdir).resolve()
    repo = Path(repo_root).resolve()
    if result["dataset_mode"] != SYNTHETIC:
        try:
            rel = out.relative_to(repo)
        except ValueError:
            rel = None
        if rel is not None and rel.parts[:2] != ("data", "private"):
            raise ValueError("External funnel output inside repo requires ignored data/private/")
    out.mkdir(parents=True, exist_ok=True)
    (out / "RESEARCH_FUNNEL.json").write_bytes(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")
    fields = ["stage", "id", "name", "isin", "sector", "market_score",
              "quality_status", "price_session", "reason"]
    h = io.StringIO(newline="")
    writer = csv.DictWriter(h, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for key in ("stage_1_pool", "stage_2_deep_dive", "stage_3_provisional_finalists"):
        for row in result[key]:
            writer.writerow({f:row[f] for f in fields})
    (out / "RESEARCH_FUNNEL.csv").write_text(h.getvalue(), encoding="utf-8")
    lines = [
        "# R-007 — Selection funnel (research only)", "",
        f"**Status:** {result['status']}",
        f"**As-of:** {result['as_of']} · **Mode:** {result['dataset_mode']}",
        f"**Universe:** {result['input_universe_count']} · "
        f"**Quality eligible:** {result['research_eligible_count']} · "
        f"**Excluded:** {result['excluded_count']}",
        f"**Stage 1:** {len(result['stage_1_pool'])} · "
        f"**Stage 2:** {len(result['stage_2_deep_dive'])} · "
        f"**Stage 3:** {len(result['stage_3_provisional_finalists'])}",
        f"**Source manifest hash:** {result['dataset_manifest_sha256']}",
        "", "**NO BUY SIGNAL. No trade-ready or independent factual certification.**",
    ]
    for key, label in (
        ("stage_1_pool", "Research pool"),
        ("stage_2_deep_dive", "Due-diligence queue"),
        ("stage_3_provisional_finalists", "Provisional finalists"),
    ):
        lines += ["", "## " + label, ""]
        for row in result[key]:
            safe_name = row["name"].replace("\n", " ").replace("|", "/")[:150]
            lines.append(f"- {row['id']} — {safe_name}: historical score {row['market_score']} "
                         "(not a recommendation)")
    lines += ["", "## Limitations", ""] + ["- " + x for x in result["limitations"]]
    (out / "RESEARCH_FUNNEL.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return out
