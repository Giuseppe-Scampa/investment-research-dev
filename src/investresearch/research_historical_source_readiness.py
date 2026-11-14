"""R-004/P0 offline historical source readiness, never an alpha or trade gate.

Reads a hash-verified local research bundle and the unmodified frozen V3
calendar. Reports only aggregate coverage, no identifiers, prices, holdings
or vendor bytes. Price coverage cannot establish licensed PIT identity,
correct delisting payouts or an independently adjusted total-return series.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from .historical_calendar_v2 import dates_v2
from .research_bundle import load_bundle, EXTERNAL, SYNTHETIC
from .research_historical_validation_v2 import preregistered_anchors, SUPPORTED_PROVIDERS, ELIGIBLE_BASIS
from .research_historical_validation_v3 import v3_protocol

SCHEMA = "R004_V3_SOURCE_READINESS_AUDIT_V1"
MAX_ASSETS = 500
ALLOWED_VENUES = frozenset(("XNYS", "XNAS", "XMIL", "XPAR", "XETR"))


def _anchor_required_sessions(day: str, venue: str, cutoff: str):
    t = date.fromisoformat(day)
    before = dates_v2(t - timedelta(days=180), t, venue)[-61:]
    after = dates_v2(t + timedelta(days=1),
                     min(t + timedelta(days=110), date.fromisoformat(cutoff)),
                     venue)
    return before, after


def audit_historical_source_readiness(bundle: Path) -> dict:
    root = Path(bundle)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Original B source bundle must be a regular directory")
    m, items, fx, events = load_bundle(root)
    if not 1 <= len(items) <= MAX_ASSETS:
        raise ValueError("Unbounded historical source universe")
    as_of = m["as_of"]
    venues = {a.get("venue") for a, _, _ in items}
    if not venues.issubset(ALLOWED_VENUES):
        raise ValueError("Historical data venue is not registered in V3")
    policy, digest = v3_protocol()
    anchors = tuple(t for t in preregistered_anchors(sorted(venues), policy) if t < as_of)
    by_venue = Counter(a["venue"] for a, _, _ in items)
    source_counts = Counter(a["prices"].get("provider") for a, _, _ in items)
    unsupported_source = sum(a["prices"].get("provider") not in SUPPORTED_PROVIDERS
                             or a["prices"].get("price_basis") not in ELIGIBLE_BASIS
                             for a, _, _ in items)
    unknown_listed = sum(not a.get("listing_date") for a, _, _ in items)
    unknown_delisted = sum(not a.get("delisted_date") for a, _, _ in items)
    unknown_isin = sum(not a.get("isin") for a, _, _ in items)
    missing_fx = bool(any(a["currency"] == "USD" for a, _, _ in items) and fx is None)
    misaligned_fx = 0
    price_sets = {}
    for a, bars, _ in items:
        if len(bars) > 3000:
            raise ValueError("Unbounded daily market history")
        price_sets[a["id"]] = frozenset(r["date"] for r in bars)
        if a["currency"] == "USD" and fx is not None:
            known = {r["date"] for r in fx}
            if any(d not in known for d in price_sets[a["id"]]):
                misaligned_fx += 1
    counts = Counter()
    no_lifecycle_on_anchor = 0
    complete_history_members = 0
    matured_complete_member_paths = 0
    matured_unresolved_member_paths = 0
    pending_member_paths = 0
    historical_anchor_dates = []
    for anchor in anchors:
        date_checked = {"anchor": anchor, "observed_61": 0,
                        "matured_complete_31": 0, "matured_unresolved_31": 0,
                        "pending_31": 0, "unverified_listing_vintage": 0,
                        "asof_excluded_by_claimed_lifecycle": 0}
        for a, _, _ in items:
            listed = a.get("listing_date")
            ended = a.get("delisted_date")
            if not listed:
                no_lifecycle_on_anchor += 1
                date_checked["unverified_listing_vintage"] += 1
                continue
            if listed > anchor or (ended and ended < anchor):
                date_checked["asof_excluded_by_claimed_lifecycle"] += 1
                continue
            required_before, possible_after = _anchor_required_sessions(anchor, a["venue"], as_of)
            if len(required_before) != 61 or required_before[-1] != anchor:
                continue
            obs = price_sets[a["id"]]
            if not set(required_before).issubset(obs):
                continue
            complete_history_members += 1
            date_checked["observed_61"] += 1
            if len(possible_after) < 31:
                pending_member_paths += 1
                date_checked["pending_31"] += 1
            elif set(possible_after[:31]).issubset(obs):
                matured_complete_member_paths += 1
                date_checked["matured_complete_31"] += 1
            else:
                matured_unresolved_member_paths += 1
                date_checked["matured_unresolved_31"] += 1
        if any(date_checked.values()):
            historical_anchor_dates.append(date_checked)
        counts["scheduled_anchors"] += 1
    # A row's listing/delisting fields are only source/operator assertions,
    # NEVER independent vintage/issuer/terminal-cash-flow authentication.
    # Even 100% coverage therefore cannot certify profitable or PIT results.
    manifest_bytes = (root / "manifest.json").read_bytes()
    result = {
        "schema_version": SCHEMA,
        "scope": "PREREGISTERED_V3_ANCHOR_COVERAGE_ONLY_NO_TRADING_OR_MODEL_REEVALUATION",
        "source_mode": m["mode"],
        "as_of": as_of,
        "v3_protocol_sha256": digest,
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "total_assets": len(items),
        "count_by_venue": dict(sorted(by_venue.items())),
        "count_by_price_provider": dict(sorted(source_counts.items())),
        "unsupported_v3_price_basis_or_provider": unsupported_source,
        "unknown_listing_date_count": unknown_listed,
        "unknown_delisted_date_count": unknown_delisted,
        "unknown_isin_count": unknown_isin,
        "usd_fx_source_missing": missing_fx,
        "usd_assets_missing_any_same_date_fx": misaligned_fx,
        "preexisting_event_rows_are_not_corporate_action_settlement_proof": len(events),
        "scheduled_v3_anchors_before_source_cutoff": len(anchors),
        "member_anchor_combinations_without_any_listing_vintage": no_lifecycle_on_anchor,
        "member_anchor_combinations_with_complete_61_day_history": complete_history_members,
        "member_anchor_combinations_with_matured_complete_31_day_path": matured_complete_member_paths,
        "member_anchor_combinations_with_matured_unresolved_31_day_path": matured_unresolved_member_paths,
        "member_anchor_combinations_with_forward_path_not_yet_matured": pending_member_paths,
        "anchor_coverage_no_security_identifiers": historical_anchor_dates,
        "source_or_operator_listing_vintage_independently_verified": False,
        "source_licence_for_research_independently_verified": False,
        "split_dividend_subscription_rights_and_delisting_proceeds_verified": False,
        "original_exchange_prices_independently_verified": False,
        "selection_model_retrained_or_reweighted": False,
        "statistical_performance_calculated": False,
        "research_readiness": "BLOCKED_SOURCE_EVIDENCE_AND_POINT_IN_TIME_INCOMPLETE",
        "synthetic_fixture_only": m["mode"] == SYNTHETIC,
        "predictive_edge_certified": False,
        "trade_ready": False,
    }
    if m["mode"] not in (SYNTHETIC, EXTERNAL):
        raise ValueError("Unsupported historical bundle mode")
    return result


def write_readiness(report: dict, output: Path, *, repo_root: Path) -> Path:
    out = Path(output).absolute()
    repo = Path(repo_root).resolve()
    if out.is_symlink() or out.exists() or not out.parent.is_dir():
        raise ValueError("Use a NEW existing output directory, no overwrite")
    if not any(out.parts[i:i+2] == ("data", "private") for i in range(len(out.parts)-1)):
        raise ValueError("Historical audit output must be private")
    if out.is_relative_to(repo) and not out.is_relative_to(repo / "data/private"):
        raise ValueError("Never write original-source audit outside ignored private B files")
    # No identifiers, market prices or original vendor bytes are included.
    content=json.dumps(report,sort_keys=True,indent=2,ensure_ascii=True)+"\n"
    with out.open("x",encoding="utf-8") as f:
        f.write(content)
    return out
