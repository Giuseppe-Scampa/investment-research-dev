"""Successor V3 preregistered same-K historical falsification (NO trading).

The frozen V1/V2 experiments are imported only for existing scoring and costs.
V3's *new* primary metric is the exact expectation of the random K-position
portfolio with K-leg fees. Its date schedule is chosen without future outcomes.
Any matured, unresolved as-of eligible member blocks positive inference;
complete-case diagnostics are always marked as potentially selected.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean, median

from .historical_calendar_v2 import dates_v2
from .research_bundle import load_bundle, SYNTHETIC, EXTERNAL
from .research_historical_validation import (
    _spearman, _adjusted_eur_prices,
)
from .research_historical_validation_v2 import (
    _eligible, _forward, _dd, _bootstrap, preregistered_anchors,
    SUPPORTED_PROVIDERS, ELIGIBLE_BASIS, MAX_ASSETS,
)
from .research_screen import WEIGHTS

PROTOCOL_V3 = (Path(__file__).resolve().parents[2] /
    "config/backtest/v3_long_horizon_protocol_v3_2026-11-11.json")
FROZEN_V3_BLOB_SHA = "2f48675b0b0d319becf360854317d05a708affb7"
SCHEMA = "V3_LONG_HORIZON_BACKTEST_V3"
MAX_HISTORY = 2000


def v3_protocol():
    raw = PROTOCOL_V3.read_bytes()
    blob = b"blob " + str(len(raw)).encode() + b"\x00" + raw
    if hashlib.sha1(blob).hexdigest() != FROZEN_V3_BLOB_SHA:
        raise ValueError("PREREGISTERED_V3_PROTOCOL_CHANGED; register a successor")
    policy = json.loads(raw)
    if (policy["schema_version"] != "v3-historical-evaluation-protocol-v3"
            or policy["comparisons"]["primary_benchmark"] !=
                "EXACT_EXPECTED_RANDOM_K_PORTFOLIO_NET_SAME_INSTRUMENTS_SAME_COSTS"
            or policy["statistics"]["primary_metric"] !=
                "MEAN_COMPLETE_FOLD_SELECTED_EXCESS_NET_VS_EXACT_SAME_K_RANDOM_EXPECTATION"
            or policy["score"]["weights_frozen"] != WEIGHTS
            or policy["cohort"]["forward_return_intervals"] != 30
            or policy["cohort"]["minimum_independent_folds_for_predictive_evidence"] != 30
            or policy["comparisons"]["selected_top_k"] != 2
            or policy["comparisons"]["random_portfolios"] != 10000
            or policy["comparisons"]["negative_control_random_walk_worlds"] != 1000
            or policy["calendar"]["required_version"] != "4.13.1"
            or policy["missing_outcomes"]["no_conditioning_on_outcome_completeness"] is not True
            or policy["statistics"]["require_zero_unresolved_matured_as_of_cohorts"] is not True):
        raise ValueError("V3 score, same-K control or missingness gate changed")
    return policy, hashlib.sha256(raw).hexdigest()


def _planned_exit(t, venues, policy):
    """Calendar-only planned expiration for each member. NEVER reads future prices."""
    future = date.fromisoformat(t) + timedelta(days=1)
    holding = policy["cohort"]["forward_return_intervals"]
    ends = []
    for venue in sorted(set(venues)):
        sessions = dates_v2(future, date(2026,12,31), venue)
        if len(sessions) < holding+1:
            raise ValueError("V3 calendar has insufficient future sessions")
        ends.append(sessions[holding])
    return max(ends)


def evaluate_v3(bundle, *, settings=None):
    policy, protocol_digest = v3_protocol()
    root = Path(bundle)
    manifest, items, fx, events = load_bundle(root)
    if (manifest["mode"] not in (SYNTHETIC, EXTERNAL) or events
            or not 3 <= len(items) <= MAX_ASSETS):
        raise ValueError("V3 requires bounded as-of priced research bundle, no hindsight events")
    if manifest["mode"] == EXTERNAL:
        for asset, _, _ in items:
            meta = asset["prices"]
            if (meta.get("provider") not in SUPPORTED_PROVIDERS
                    or meta.get("price_basis") not in ELIGIBLE_BASIS):
                raise ValueError("V3 original adjusted source not authorized; Tiingo Starter forbidden")
    settings = settings or {
        "exclude_primary_oil": True, "exclude_additional_gold": True,
        "avoid_duplicate_eurostoxx50": True,
    }
    aligned = {}
    for asset, bars, _ in items:
        converted = _adjusted_eur_prices(asset, bars, fx)
        if converted is None:
            raise ValueError("V3 missing same-day original EUR FX")
        if len(converted) > MAX_HISTORY:
            raise ValueError("V3 original historical series exceeds bounded cap")
        if asset["id"] in aligned:
            raise ValueError("Duplicate V3 original research identity")
        aligned[asset["id"]] = (asset, converted)
    anchors = preregistered_anchors(
        [asset["venue"] for asset, _, _ in items], policy)
    as_of = manifest["as_of"]
    k = policy["comparisons"]["selected_top_k"]
    results = []
    anchor_audit = []
    rejected = []
    # This boundary is reserved before future data inspection, even if a
    # matured fold later fails. Outcome completeness cannot change scheduling.
    previous_reserved_exit = None
    matured_count = 0
    unresolved_matured_count = 0
    unresolved_matured_member_count = 0
    pending_count = 0
    as_of_insufficient_count = 0
    for t in anchors:
        if t >= as_of:
            anchor_audit.append({
                "date": t, "state": "FUTURE_RELATIVE_TO_SOURCE_AS_OF",
                "eligible": None, "planned_exit_date": None,
            })
            continue
        if previous_reserved_exit is not None and t <= previous_reserved_exit:
            anchor_audit.append({
                "date": t, "state": "EX_ANTE_OVERLAPPING_ANCHOR",
                "eligible": None, "planned_exit_date": None,
            })
            continue
        available = []
        for asset, rows in aligned.values():
            candidate = _eligible(asset, rows, t, settings)
            if candidate is not None:
                available.append(candidate)
        if len(available) < max(3, k+1):
            as_of_insufficient_count += 1
            rejected.append([t, "INSUFFICIENT_PRE_OUTCOME_AS_OF_UNIVERSE"])
            anchor_audit.append({
                "date": t, "state": "INSUFFICIENT_AS_OF_UNIVERSE",
                "eligible": len(available), "planned_exit_date": None,
            })
            continue
        ranked = sorted(available, key=lambda x: (-x["score"], x["id"]))
        chosen, bottom = ranked[:k], ranked[-k:]
        planned_exit = _planned_exit(t, [r["venue"] for r in ranked], policy)
        previous_reserved_exit = planned_exit
        cohort_sha = hashlib.sha256(
            json.dumps([r["id"] for r in ranked], ensure_ascii=False,
                       separators=(",", ":")).encode()).hexdigest()
        audit = {
            "date": t, "eligible": len(ranked),
            "as_of_cohort_sha256": cohort_sha,
            "selected_ids_as_of": [r["id"] for r in chosen],
            "bottom_ids_as_of": [r["id"] for r in bottom],
            "planned_exit_date": planned_exit,
        }
        if planned_exit > as_of:
            pending_count += 1
            audit["state"] = "OUTCOME_NOT_MATURED_AS_OF_CUTOFF"
            anchor_audit.append(audit)
            continue
        matured_count += 1
        # Every eligible security is checked; skipping losers after seeing
        # future coverage would be survivorship selection. No imputation.
        observed = {}
        missing_ids = []
        for member in ranked:
            outcome = _forward(
                member, aligned[member["id"]][1], t, policy,
                policy["costs"]["notional_eur"]/k)
            if outcome is None:
                missing_ids.append(member["id"])
            else:
                observed[member["id"]] = outcome
        if missing_ids:
            unresolved_matured_count += 1
            unresolved_matured_member_count += len(missing_ids)
            audit["state"] = "MATURED_OUTCOME_UNRESOLVED_FAIL_CLOSED"
            audit["unresolved_ids"] = missing_ids
            audit["unresolved_count"] = len(missing_ids)
            audit["unresolved_selected_ids"] = sorted(
                set(missing_ids) & {c["id"] for c in chosen})
            rejected.append([t, "MATURED_OUTCOME_UNRESOLVED_DO_NOT_DROP_ASSETS"])
            anchor_audit.append(audit)
            continue
        audit["state"] = "MATURED_COMPLETE"
        audit["unresolved_ids"] = []
        audit["unresolved_count"] = 0
        anchor_audit.append(audit)
        same_k_selected = mean(observed[c["id"]]["net"] for c in chosen)
        inverse = mean(observed[c["id"]]["net"] for c in bottom)
        # Exact expected random-K net return. Linear expectation of a
        # uniformly sampled K-security subset equals the N-name mean, but
        # EACH constituent is costed with the K-leg notional, not N-leg fees.
        random_k_expected = mean(x["net"] for x in observed.values())
        # The old N-leg comparator stays descriptive ONLY, never the gate.
        n_leg = []
        for member in ranked:
            q = _forward(
                member, aligned[member["id"]][1], t, policy,
                policy["costs"]["notional_eur"]/len(ranked))
            if q is None:
                raise ValueError("V3 future-path validity depends on leg size")
            n_leg.append(q["net"])
        n_leg_mean = mean(n_leg)
        ic = _spearman(
            [member["score"] for member in ranked],
            [observed[member["id"]]["gross"] for member in ranked])
        result = {
            "date": t, "exit_date": planned_exit, "eligible": len(ranked),
            "as_of_cohort_sha256": cohort_sha,
            "selected_ids": [member["id"] for member in chosen],
            "bottom_ids": [member["id"] for member in bottom],
            "selected_net": round(same_k_selected,8),
            "bottom_net": round(inverse,8),
            "same_K_random_expected_net": round(random_k_expected,8),
            "excess": round(same_k_selected-random_k_expected,8),
            "same_K_excess_net": round(same_k_selected-random_k_expected,8),
            "N_leg_descriptive_net": round(n_leg_mean,8),
            "N_leg_descriptive_excess": round(same_k_selected-n_leg_mean,8),
            "ic": round(ic,8) if ic is not None else None,
            "max_drawdown": round(_dd(
                [observed[c["id"]]["curve"] for c in chosen]),8),
            "selection_above_median_rate": round(mean(
                observed[c["id"]]["gross"] >
                median(x["gross"] for x in observed.values()) for c in chosen),4),
            "_candidate_net": {r["id"]:observed[r["id"]]["net"] for r in ranked},
        }
        results.append(result)
    rng = random.Random(policy["comparisons"]["random_seed"])
    random_pool = []
    if results:
        for _ in range(policy["comparisons"]["random_portfolios"]):
            draws = []
            for fold in results:
                ids = rng.sample(tuple(fold["_candidate_net"]), k)
                draws.append(mean(fold["_candidate_net"][identity] for identity in ids))
            random_pool.append(mean(draws))
    selected = mean(f["selected_net"] for f in results) if results else None
    percentile = (sum(val < selected for val in random_pool)/len(random_pool)
                  if random_pool else None)
    primary_ci, ic_ci = _bootstrap(results, policy)
    descriptive_ci, _ = _bootstrap(
        [{"excess":f["N_leg_descriptive_excess"],"ic":f["ic"]} for f in results],
        policy)
    enough = bool(
        len(results) >= policy["cohort"]["minimum_independent_folds_for_predictive_evidence"]
        and all(f["eligible"] >= policy["cohort"]["minimum_eligible_instruments"]
                for f in results))
    primary_diagnostic = bool(
        enough and unresolved_matured_count == 0 and primary_ci and ic_ci
        and primary_ci[0] > 0 and ic_ci[0] > 0
        and percentile is not None
        and percentile >= policy["statistics"]["random_portfolio_percentile_at_least"]
        and mean(f["selected_net"]-f["bottom_net"] for f in results) > 0)
    for fold in results:
        del fold["_candidate_net"]
    return {
        "schema_version": SCHEMA,
        "preregistered_protocol_sha256": protocol_digest,
        "protocol_git_blob_sha": FROZEN_V3_BLOB_SHA,
        "input_manifest_sha256": hashlib.sha256(
            (root/"manifest.json").read_bytes()).hexdigest(),
        "status": ("SYNTHETIC_NO_MARKET_EVIDENCE" if manifest["mode"] == SYNTHETIC
                   else "REAL_SOURCE_RETROSPECTIVE_DATA_RIGHTS_AND_VINTAGE_REVIEW_REQUIRED"),
        "as_of": as_of,
        "primary_benchmark": policy["comparisons"]["primary_benchmark"],
        "primary_metric": policy["statistics"]["primary_metric"],
        "planned_decision_anchors": len(anchors),
        "as_of_insufficient_anchors": as_of_insufficient_count,
        "matured_as_of_eligible_anchors": matured_count,
        "matured_outcome_unresolved_anchors": unresolved_matured_count,
        "matured_outcome_unresolved_asset_events": unresolved_matured_member_count,
        "pending_not_yet_matured_anchors": pending_count,
        "ex_ante_anchor_audit": anchor_audit,
        "rejections": rejected,
        "complete_nonoverlapping_folds": len(results),
        "folds": results,
        "mean_net_selected": round(selected,8) if selected is not None else None,
        "same_K_expected_random_net_mean": round(
            mean(f["same_K_random_expected_net"] for f in results),8) if results else None,
        "same_K_excess_net_mean_PRIMARY": round(
            mean(f["same_K_excess_net"] for f in results),8) if results else None,
        "confidence_interval_95_same_K_excess_PRIMARY": primary_ci,
        "confidence_interval_95_ic": ic_ci,
        "N_leg_descriptive_excess_mean_DO_NOT_USE_AS_ALPHA": round(
            mean(f["N_leg_descriptive_excess"] for f in results),8) if results else None,
        "N_leg_descriptive_CI_DO_NOT_USE_AS_ALPHA": descriptive_ci,
        "mean_rank_IC": round(
            mean(f["ic"] for f in results if f["ic"] is not None),8)
            if any(f["ic"] is not None for f in results) else None,
        "random_portfolio_trials": len(random_pool),
        "random_percentile": round(percentile,6) if percentile is not None else None,
        "minimum_fold_and_universe_power_met": enough,
        "primary_diagnostic_gate_without_null_control": primary_diagnostic,
        "matured_outcome_completeness_gate": unresolved_matured_count == 0,
        "statistical_diagnostic_gate_without_null_control": primary_diagnostic,
        "random_walk_false_positive_rate_calibrated": False,
        "historical_corporate_actions_independently_verified": False,
        "historical_point_in_time_universe_independently_verified": False,
        "data_rights_independently_verified": False,
        "italian_tax_by_isin_verified": False,
        "historical_folds_are_retrospective_not_prospective": True,
        "predictive_edge_certified": False,
        "trade_ready": False,
        "limitations": [
            "V3 registered after viewing V2 and its prior pilot: not an untouched historical holdout.",
            "Any missing outcome in an as-of eligible matured cohort blocks positive statistics.",
            "Complete-fold estimates may be censored/selected when missing data exists; never certify.",
            "Delisting payouts need authenticated terminal settlement; unsupported outcomes fail closed.",
            "N-leg grossly unequal ticket-size fee comparator is descriptive and excluded from acceptance.",
            "Missing PIT and corporate action verification, provider licence and broker tax evidence.",
            "No retrospective or synthetic statistical advantage qualifies as prospective predictive edge.",
        ],
    }
