"""Decision 2026: audited short-horizon *research queue* from Block B.

This is not the permanent R-007 200+ funnel. It REUSES screen() and R-007
candidate gates, never accepts hand-authored ranking/score inputs and never
modifies the R-007 200/100/40/6 thresholds. The local private Block A remains
authoritative for portfolio, cash, taxes and broker execution assumptions.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from .research_bundle import EXTERNAL, SYNTHETIC
from .research_funnel import _eligible
from .tax_engine import FiscalRegistry, CAPITAL, DIFFERENT, UNKNOWN

VERSION = "decision-2026-tactical-research-v1"
LIMIT = 12
TYPE_QUOTA = 4
DEADLINE = date(2026, 12, 31)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _tax(asset_type, isin, as_of, fiscal_registry):
    """Research category, never a broker or ISIN-specific tax certification."""
    try:
        rule = fiscal_registry.get(asset_type, as_of, isin)
    except ValueError:
        return {
            "gain_category": UNKNOWN, "tax_research_status": "MISSING_OR_AMBIGUOUS_FISCAL_RULE",
            "rule_id": None, "specific_isin_verification": False,
            "taxable_factor": None, "source_url": None,
        }
    # DOCUMENTED_GENERIC is NOT specific-ISIN or Mediolanum verification.
    verified_isin = bool(rule.isin and rule.isin == isin
                         and rule.verification not in ("ISIN_REVIEW_REQUIRED", "DOCUMENTED_GENERIC"))
    return {
        "gain_category": rule.gain_category,
        "tax_research_status": ("ISIN_SPECIFIC_RULE_NEEDS_BROKER_CONFIRMATION" if verified_isin
                                else "GENERIC_RULE_NOT_BROKER_VERIFIED" if rule.gain_category != UNKNOWN
                                else "ISIN_TAX_REVIEW_REQUIRED"),
        "rule_id": rule.rule_id,
        "specific_isin_verification": verified_isin,
        "taxable_factor": str(rule.taxable_factor),
        "source_url": rule.source_url,
    }


def build_tactical(screening, *, fiscal_registry):
    """Triage a *source-defined cohort*, not a claim of global discovery.

    Screen's real-source score/rank cannot be substituted with authored JSON:
    callers must call screen() from a hash-verified local bundle. Nothing
    emitted here is a buy signal, forecast or actual tax-wallet application.
    """
    if not isinstance(screening, dict) or screening.get("schema_version") != 1:
        raise ValueError("Expected audited Block B screening schema v1")
    mode = screening.get("dataset_mode")
    if mode not in (EXTERNAL, SYNTHETIC):
        raise ValueError("Invalid source dataset mode")
    try:
        as_of = date.fromisoformat(screening["as_of"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Expected valid screening as_of") from None
    if as_of.year != 2026 or as_of > DEADLINE:
        raise ValueError("Decision 2026 requires an as-of date within 2026")
    rows = screening.get("results")
    if not isinstance(rows, list) or len(rows) > 5000 or screening.get("universe_size") != len(rows):
        raise ValueError("Screening row count/integrity is inconsistent")
    hashvalue = screening.get("dataset_manifest_sha256")
    if not isinstance(hashvalue, str) or len(hashvalue) != 64 or any(c not in "0123456789abcdef" for c in hashvalue):
        raise ValueError("Missing research manifest SHA-256")
    if not isinstance(fiscal_registry, FiscalRegistry):
        raise ValueError("FiscalRegistry required; no guessed tax mappings")
    ids = set()
    excluded, eligible = [], []
    by_type = Counter()
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str):
            raise ValueError("Malformed candidate")
        key = r["id"]
        if not key or len(key) > 128 or key in ids:
            raise ValueError("Duplicate, empty or oversized candidate id")
        ids.add(key)
        typ = r.get("asset_type", "UNKNOWN")
        if not isinstance(typ, str) or len(typ) > 64:
            raise ValueError("Invalid asset type")
        by_type[typ] += 1
        problems = _eligible(r, mode)
        if problems:
            excluded.append({"id": key, "asset_type": typ, "reasons": problems})
        else:
            eligible.append(r)

    # Demonstrations are deliberately NOT a tactical recommendation, despite
    # having synthetic scores and valid simulation paths.
    real = mode == EXTERNAL
    selected = []
    if real:
        groups = defaultdict(list)
        for row in eligible:
            groups[row["asset_type"]].append(row)
        for values in groups.values():
            values.sort(key=lambda r: (-r["market_score"], r["id"]))
        # Never compare cross-asset market_score as an expected-return proxy.
        # Choose diverse *review coverage*: one per class per round.
        active = sorted(groups)
        for ix in range(TYPE_QUOTA):
            for asset_type in active:
                if ix < len(groups[asset_type]):
                    selected.append(groups[asset_type][ix])
        selected = selected[:LIMIT]
    priorities = []
    for r in selected:
        tx = _tax(r["asset_type"], r.get("isin", ""), as_of, fiscal_registry)
        m = r.get("market_metrics") or {}
        metrics = {}
        for field in ("volatility_20", "max_drawdown_60", "momentum_20",
                      "momentum_60", "avg_daily_turnover_eur_20"):
            val = m.get(field)
            if type(val) in (int, float) and val == val and abs(val) != float("inf"):
                metrics[field] = val
            else:
                metrics[field] = None
        gaps = [
            "EXECUTABLE_BID_ASK_AND_MEDIOLANUM_FEES_NOT_VERIFIED",
            "SOURCE_LICENSE_AND_CORPORATE_ACTIONS_NOT_INDEPENDENTLY_CERTIFIED",
            "NO_EXPECTED_RETURN_OR_VALUATION_FORECAST",
            "NO_ISIN_SPECIFIC_BROKER_TAX_CERTIFICATION",
            "NO_DEC_2026_REALIZATION_ASSURANCE",
            "NO_CROSS_ASSET_RISK_COMPARABILITY",
        ]
        if tx["gain_category"] == CAPITAL:
            gaps.append("ETF_OR_OTHER_CAPITAL_INCOME_GAINS_CANNOT_USE_LOSS_WALLET")
        elif tx["gain_category"] == UNKNOWN:
            gaps.append("FISCAL_COMPENSABILITY_UNVERIFIED")
        priorities.append({
            "id": r["id"], "name": r["name"], "isin": r["isin"],
            "asset_type": r["asset_type"], "venue": r["venue"],
            "sector": r["sector"], "currency": r["currency"],
            "price_source_url": r["price_source_url"],
            "price_sha256": r["price_sha256"],
            "last_price_session": r["last_price_session"],
            "historical_market_score": r["market_score"],
            "market_risk_proxies_not_forecasts": metrics,
            "fiscal_gain_research": tx,
            "warnings": list(r.get("warnings") or []),
            "blocking_evidence_gaps": gaps,
            "queue_reason": "Priority within its asset type based on existing R-008 historical screening",
            "trade_ready": False, "recommendation": "NONE",
        })
    coverage = {"submitted_by_asset_type": dict(sorted(by_type.items())),
                "eligible_by_asset_type": dict(sorted(Counter(r["asset_type"] for r in eligible).items())),
                "coverage_claim": "SOURCE_DEFINED_COHORT_NOT_GLOBAL_INDEPENDENT_DISCOVERY"}
    if not real:
        status = "SYNTHETIC_DIAGNOSTIC_NO_INVESTMENT_QUEUE"
    elif not priorities:
        status = "REAL_DATA_INSUFFICIENT_NO_RESEARCH_PRIORITIES"
    else:
        status = "PROVISIONAL_TACTICAL_RESEARCH_PRIORITIES_NOT_TRADE_READY"
    return {
        "schema_version": VERSION, "as_of": as_of.isoformat(),
        "deadline": DEADLINE.isoformat(),
        "dataset_mode": mode,
        "dataset_manifest_sha256": hashvalue,
        "screening_sha256": hashlib.sha256(_canonical(screening)).hexdigest(),
        "status": status,
        "trade_ready": False,
        "final_investment_shortlist": [],
        "instrument_count": len(rows),
        "research_eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "exclusions": excluded,
        "coverage": coverage,
        "research_priorities_by_type": priorities,
        "tax_wallet_status": "NOT_APPLIED_REQUIRES_PRIVATE_BLOCK_A",
        "r007_global_funnel_status": "UNCHANGED_NOT_SUBSTITUTED",
        "method": "Existing source-validated R-008 screen and R-007 per-instrument gates; round-robin *within* asset class, not an expected-return cross-class comparison",
        "limitations": [
            "No subset of sources establishes broad unbiased market coverage; no top investment claim.",
            "A tax gain category is not proof of ISIN-specific eligibility or of gains before expiry.",
            "Neither sample cohort scores nor historical volatility forecast Nov-Dec returns.",
            "Short-horizon risk and trading venue bid/ask, liquidity and fees require separate review.",
            "Private Block A must calculate tax/cost/Scenario C using actual account inputs.",
            "No auto-trading, no guaranteed use of 2022 losses by 2026-12-31.",
        ],
    }


def _csv_safe(value):
    s = "" if value is None else str(value)
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s


def write_tactical(report, output, *, repo_root):
    """Never write real-source report into a tracked repo path."""
    out = Path(output).resolve()
    root = Path(repo_root).resolve()
    if report["dataset_mode"] != SYNTHETIC:
        try:
            rel = out.relative_to(root)
        except ValueError:
            rel = None
        if rel is not None and rel.parts[:2] != ("data", "private"):
            raise ValueError("External tactical outputs in repo must be under ignored data/private/")
    out.mkdir(parents=True, exist_ok=True)
    (out / "TACTICAL_RESEARCH.json").write_bytes(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    columns = ["id", "name", "isin", "asset_type", "venue", "historical_market_score",
               "last_price_session", "gain_category", "tax_research_status", "trade_ready"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for item in report["research_priorities_by_type"]:
        obj = {k:item.get(k) for k in columns}
        obj["gain_category"] = item["fiscal_gain_research"]["gain_category"]
        obj["tax_research_status"] = item["fiscal_gain_research"]["tax_research_status"]
        writer.writerow({k:_csv_safe(v) for k,v in obj.items()})
    (out / "TACTICAL_RESEARCH.csv").write_text(stream.getvalue(), encoding="utf-8")
    lines = [
        "# Decision 2026 — Tactical research audit, NOT investment shortlist",
        "", f"**Mode:** {report['dataset_mode']} · **Status:** {report['status']}",
        f"**As-of:** {report['as_of']} · **Deadline:** {report['deadline']}",
        f"**Universe submitted:** {report['instrument_count']}",
        f"**Research eligible:** {report['research_eligible_count']} · **Excluded:** {report['excluded_count']}",
        f"**Source manifest SHA-256:** {report['dataset_manifest_sha256']}",
        "", "## Priority for further independent verification (not purchase orders)", "",
    ]
    for row in report["research_priorities_by_type"]:
        title=html.escape(str(row["name"]).replace("\n", " ").replace("|", "/")[:150])
        lines.append(f"- {title} ({html.escape(row['id'])}): class "
                     f"{html.escape(row['asset_type'])}, historical score {row['historical_market_score']}; "
                     f"fiscal gain = {row['fiscal_gain_research']['gain_category']}, "
                     "NO TRADE READY")
    lines += ["", "## Gaps / limitations", ""] + ["- " + html.escape(s) for s in report["limitations"]]
    (out / "TACTICAL_RESEARCH.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return out
