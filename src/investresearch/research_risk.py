"""Cross-candidate historical correlation audit from the exact screened bundle.

No forecasting, cross-asset portfolio recommendation, ticker-only identity
mapping or unlicensed source fetching. Pair correlations are diagnostics:
asynchronous US/EU closes and ECB fixings prohibit synchronous-P/L claims.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import mean

from .research_bundle import load_bundle, SYNTHETIC
from .research_screen import _fx_dated_prices, screen
from .tactical_research import build_tactical

VERSION = "r008-paired-returns-risk-v1"
MIN_RETURN_OBSERVATIONS = 20
MAX_PAIR_CANDIDATES = 12


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _correlation(xs, ys):
    if len(xs) != len(ys) or len(xs) < MIN_RETURN_OBSERVATIONS:
        raise ValueError("Insufficient aligned return observations")
    ax, ay = mean(xs), mean(ys)
    vx = sum((x - ax)**2 for x in xs)
    vy = sum((y - ay)**2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return round(max(-1.0, min(1.0, sum(
        (x - ax)*(y - ay) for x, y in zip(xs, ys)
    ) / math.sqrt(vx*vy))), 6)


def analyze_risk(bundle: Path, screening: dict, tactical: dict):
    """Use only screened/selected source identities, not a caller's price CSV."""
    manifest, items, fx, _events = load_bundle(Path(bundle))
    original_sha = hashlib.sha256((Path(bundle)/"manifest.json").read_bytes()).hexdigest()
    if (screening.get("dataset_manifest_sha256") != original_sha
            or tactical.get("dataset_manifest_sha256") != original_sha
            or screening.get("dataset_mode") != manifest["mode"]
            or tactical.get("dataset_mode") != manifest["mode"]
            or screening.get("as_of") != manifest["as_of"]
            or tactical.get("as_of") != manifest["as_of"]
            or tactical.get("screening_sha256") != canonical_sha(screening)):
        raise ValueError("Risk input does not match original source/Screen/Tactical")
    rows = screening.get("results")
    if not isinstance(rows, list) or screening.get("universe_size") != len(rows):
        raise ValueError("Risk screening row count inconsistent")
    if manifest["mode"] == SYNTHETIC:
        if tactical.get("research_priorities_by_type") != []:
            raise ValueError("Synthetic test cannot be promoted to tactical priorities")
        eligible = sorted(
            (r for r in rows if r.get("market_score") is not None
             and r.get("status") == "DEMO_RANK_NOT_REAL_MARKET"),
            key=lambda r: (-r["market_score"], r["id"]),
        )[:MAX_PAIR_CANDIDATES]
        source = "SYNTHETIC_DIAGNOSTIC_ONLY"
    else:
        ids = [r["id"] for r in tactical.get("research_priorities_by_type", [])]
        if len(ids) > MAX_PAIR_CANDIDATES or len(ids) != len(set(ids)):
            raise ValueError("Risk candidates exceed explicit tactical limit")
        lookup = {r["id"]: r for r in rows}
        if len(lookup) != len(rows) or any(
            uid not in lookup or lookup[uid].get("status") != "RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY"
            for uid in ids
        ):
            raise ValueError("Risk candidates not backed by ranked screening")
        eligible = [lookup[uid] for uid in ids]
        source = "SOURCE_DEFINED_TACTICAL_UNVERIFIED_NOT_TRADE_READY"

    item_lookup = {asset["id"]: (asset, bars) for asset, bars, _facts in items}
    by_id = {}
    for row in eligible:
        if row["id"] not in item_lookup:
            raise ValueError("Ranked risk candidate missing from source bundle")
        asset, bars = item_lookup[row["id"]]
        aligned, issue = _fx_dated_prices(bars, fx, asset["currency"])
        if issue or len(aligned) < 61:
            # Screen independently enforces source calendar/FX constraints.
            raise ValueError("Ranked risk candidate lacks 61 aligned source sessions")
        by_id[row["id"]] = {
            "observations": {d: Decimal(p) for d, p, _v in aligned[-61:]},
            "currency": asset["currency"],
            "venue": asset["venue"],
            "asset_type": row["asset_type"],
            "sector": row.get("sector", ""),
            "isin": row.get("isin", ""),
        }

    pairs = []
    for i, first in enumerate(eligible):
        for second in eligible[i+1:]:
            a, b = by_id[first["id"]], by_id[second["id"]]
            common = sorted(set(a["observations"]) & set(b["observations"]))
            common = common[-61:]
            changes_a = [float(a["observations"][common[j]] /
                               a["observations"][common[j-1]] - 1)
                         for j in range(1, len(common))]
            changes_b = [float(b["observations"][common[j]] /
                               b["observations"][common[j-1]] - 1)
                         for j in range(1, len(common))]
            n = len(changes_a)
            correlation = _correlation(changes_a, changes_b) if n >= MIN_RETURN_OBSERVATIONS else None
            notes = ["CLOSE_TO_CLOSE_HISTORICAL_NOT_EXPECTED_RETURN"]
            if a["venue"] != b["venue"]:
                notes.append("VENUE_CLOSES_NOT_SYNCHRONOUS")
            if a["currency"] != "EUR" or b["currency"] != "EUR":
                notes.append("ECB_FX_FIXING_ASYNCHRONOUS")
            if a["asset_type"] != b["asset_type"]:
                notes.append("CROSS_ASSET_PAYOFFS_NOT_COMPARABLE")
            if n < MIN_RETURN_OBSERVATIONS:
                notes.append("INSUFFICIENT_COMMON_RETURN_OBSERVATIONS")
            if n < 60:
                notes.append("DIFFERENT_SESSION_CALENDARS_OR_GAPS")
            if correlation is None and n >= MIN_RETURN_OBSERVATIONS:
                notes.append("CONSTANT_RETURN_SERIES_CORRELATION_UNDEFINED")
            pairs.append({
                "id_a": first["id"], "id_b": second["id"],
                "isin_a": a["isin"], "isin_b": b["isin"],
                "return_observations": n,
                "first_common_session": common[0] if common else None,
                "last_common_session": common[-1] if common else None,
                "correlation_eur_eod_historical": correlation,
                "same_sector_label": bool(a["sector"] and a["sector"] == b["sector"]),
                "absolute_correlation_ge_080": abs(correlation) >= .8 if correlation is not None else None,
                "notes": notes, "trade_ready": False,
            })
    # Measure actual provider coverage rather than treating a 40-ISIN
    # discovery sample as 40 market-screened instruments.
    counts_by_type = {}
    types = sorted({r.get("asset_type", "UNKNOWN") for r in rows})
    for typ in types:
        group = [r for r in rows if r.get("asset_type", "UNKNOWN") == typ]
        ranked = sum(r.get("market_score") is not None for r in group)
        counts_by_type[typ] = {
            "submitted": len(group),
            "market_screened": ranked,
            "not_screened": len(group)-ranked,
        }
    warnings_count = Counter(
        str(w) for row in rows for w in (row.get("warnings") or [])
    )
    return {
        "schema_version": VERSION,
        "as_of": manifest["as_of"],
        "dataset_mode": manifest["mode"],
        "dataset_manifest_sha256": original_sha,
        "screening_sha256": canonical_sha(screening),
        "tactical_sha256": canonical_sha(tactical),
        "price_coverage_by_asset_type": counts_by_type,
        "screening_warning_counts": dict(sorted(warnings_count.items())),
        "selected_ids": [r["id"] for r in eligible],
        "selected_count": len(eligible),
        "pairs_count": len(pairs),
        "comparable_pairs": sum(p["correlation_eur_eod_historical"] is not None for p in pairs),
        "risk_scope": source,
        "pairs": pairs,
        "limitations": [
            "Historical EUR EOD correlation is descriptive, not a return/risk forecast.",
            "ECB FX reference fixing and US equity closing prices are asynchronous.",
            "Overlapping date observations are not guaranteed identical trading hours.",
            "No holdings weights, notional leverage, live bid-ask, counterparty or product payoff stress.",
            "Any synthetic result is entirely fictitious, not a product correlation.",
            "Low observed correlation cannot certify diversification or absence of factor concentration.",
        ],
        "trade_ready": False,
        "portfolio_approved": False,
    }


def write_risk(report: dict, output: Path, *, repo_root: Path):
    out = Path(output).resolve()
    root = Path(repo_root).resolve()
    if report.get("dataset_mode") != SYNTHETIC:
        if out.is_relative_to(root) and not out.is_relative_to(root/"data/private"):
            raise ValueError("External market risk output inside repo must be private")
    out.mkdir(parents=True, exist_ok=True)
    (out/"BLOCK_B_RISK.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+"\n",
        encoding="utf-8")
    return out
