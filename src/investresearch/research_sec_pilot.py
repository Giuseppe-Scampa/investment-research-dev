"""SEC-only live research pilot: current US ticker associations and annual filings.

The output is evidence coverage, NOT a valuation, investment ranking, or backtest.
Raw source responses stay in a locally ignored cache; no secret is serialized.
"""
from __future__ import annotations

import csv
import io
import json
import re
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

from .research_sources import (
    SEC_HOST, SEC_TICKERS_URL, MAX_BYTES, collect, parse_sec_fundamentals,
    parse_sec_annual_comparison,
    sha256_bytes,
)
from .research_universe import parse_sec_tickers

MAX_SYMBOLS = 24
MAX_ANNUAL_AGE_DAYS = 550
SYMBOL_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,15}\Z")


def parse_symbols(value: str):
    """Small, explicit symbol selection. No automated universe-wide API requests."""
    if not isinstance(value, str):
        raise ValueError("Symbols must be a comma-separated string")
    symbols = [x.strip().upper() for x in value.split(",")]
    if not (1 <= len(symbols) <= MAX_SYMBOLS):
        raise ValueError(f"Select between 1 and {MAX_SYMBOLS} SEC-listed symbols")
    if any(not SYMBOL_RE.fullmatch(x) for x in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError("Empty, duplicate or invalid SEC symbol")
    return symbols


def _read_source(meta: dict, provider: str, url: str, as_of: date):
    """Require collector provenance, correct vendor URL, intact payload and as-of."""
    if meta.get("provider") != provider or meta.get("source_url") != url:
        raise ValueError("Missing or incorrect SEC source identity")
    retrieved = meta.get("retrieved_at_utc", "")
    if not isinstance(retrieved, str):
        raise ValueError("Missing SEC source collection timestamp")
    try:
        day = date.fromisoformat(retrieved[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid SEC source collection timestamp") from exc
    if day > as_of:
        raise ValueError("SEC snapshot acquired after as-of cutoff")
    path = Path(meta["path"])
    if path.is_symlink() or not path.is_file():
        raise ValueError("Invalid SEC cache path")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_BYTES or sha256_bytes(raw) != meta.get("sha256"):
        raise ValueError("SEC cached payload does not match its checksum")
    return raw


def analyze_sec_evidence(catalog_meta: dict, company_metas: dict,
                         selected_symbols: list[str], as_of: date):
    """Compute a point-in-time SEC research coverage table from cached filings.

    Company metadata is keyed by SEC CIK to avoid ambiguities between listings.
    Multiple catalog records for the same ticker make it ineligible for inference.
    """
    if as_of > date.today():
        raise ValueError("Cannot construct a future-dated live SEC study")
    if not selected_symbols or len(selected_symbols) > MAX_SYMBOLS:
        raise ValueError("Invalid pilot selection size")
    if any(not SYMBOL_RE.fullmatch(x) for x in selected_symbols) or len(set(selected_symbols)) != len(selected_symbols):
        raise ValueError("Invalid or duplicate selected symbol")
    catalog_bytes = _read_source(catalog_meta, "SEC_TICKERS", SEC_TICKERS_URL, as_of)
    catalog = parse_sec_tickers(catalog_bytes)
    matched = {}
    for entry in catalog:
        if entry["ticker"].upper() in selected_symbols:
            matched.setdefault(entry["ticker"].upper(), []).append(entry)
    findings = []
    for ticker in selected_symbols:
        listings = matched.get(ticker, [])
        if len(listings) != 1:
            findings.append({"ticker": ticker, "status": "UNMAPPED_OR_AMBIGUOUS_TICKER",
                             "cik": "", "name": "", "exchange": "", "venue": "",
                             "period_end": "", "filing_date": "", "revenue_usd": "",
                             "net_income_usd": "", "net_margin_pct": "",
                             "filing_accession": "", "source_url": "", "source_sha256": "",
                             "comparison_status": "", "previous_period_end": "",
                             "previous_revenue_usd": "", "previous_net_income_usd": "",
                             "revenue_yoy_pct": "", "net_income_yoy_pct": "",
                             "net_margin_change_pp": "", "annual_age_days": ""})
            continue
        issuer = listings[0]
        cik = issuer["cik"]
        url = SEC_HOST + f"CIK{cik}.json"
        meta = company_metas.get(cik)
        row = {"ticker": ticker, "cik": cik, "name": issuer["name"],
               "exchange": issuer["exchange"], "venue": issuer["venue"],
               "status": "NOT_RESEARCH_READY", "period_end": "", "filing_date": "",
               "revenue_usd": "", "net_income_usd": "", "net_margin_pct": "",
               "filing_accession": "", "source_url": url, "source_sha256": "",
               "comparison_status": "", "previous_period_end": "",
               "previous_revenue_usd": "", "previous_net_income_usd": "",
               "revenue_yoy_pct": "", "net_income_yoy_pct": "",
               "net_margin_change_pp": "", "annual_age_days": ""}
        if issuer["venue"] == "UNMAPPED":
            row["status"] = "UNSUPPORTED_VENUE"
        elif meta is None:
            row["status"] = "COMPANYFACTS_NOT_ACQUIRED"
        else:
            raw = _read_source(meta, "SEC_COMPANYFACTS", url, as_of)
            body = json.loads(raw)
            if not isinstance(body, dict) or str(body.get("cik")) != str(int(cik)):
                raise ValueError("SEC companyfacts CIK mismatch")
            row["source_sha256"] = meta["sha256"]
            try:
                fact = parse_sec_fundamentals(raw, as_of)
                revenue = Decimal(fact["revenue_usd"])
                income = Decimal(fact["net_income_usd"])
                if (not revenue.is_finite() or revenue <= 0 or not income.is_finite()):
                    raise ValueError("Invalid SEC annual financial metrics")
                margin = ((income / revenue) * 100).quantize(Decimal("0.01"))
                if not margin.is_finite():
                    raise ValueError("Invalid annual net margin")
                comparison = parse_sec_annual_comparison(raw, as_of, fact)
                age = (as_of - date.fromisoformat(fact["period_end"])).days
                if age < 0:
                    raise ValueError("Annual period ends after as_of")
            except ValueError:
                row["status"] = "REVIEW_SEC_ANNUAL_FACTS_UNAVAILABLE"
            else:
                row.update({"status": ("SEC_ANNUAL_EVIDENCE_AVAILABLE_NO_MARKET_RANK"
                              if age <= MAX_ANNUAL_AGE_DAYS
                              else "SEC_ANNUAL_STALE_REVIEW_NO_MARKET_RANK"),
                    "annual_age_days": age,
                    "comparison_status": comparison["status"],
                    "previous_period_end": comparison.get("previous_period_end") or "",
                    "previous_revenue_usd": comparison.get("previous_revenue_usd") or "",
                    "previous_net_income_usd": comparison.get("previous_net_income_usd") or "",
                    "revenue_yoy_pct": comparison.get("revenue_yoy_pct") or "",
                    "net_income_yoy_pct": comparison.get("net_income_yoy_pct") or "",
                    "net_margin_change_pp": comparison.get("net_margin_change_pp") or "",
                    "period_end": fact["period_end"],
                    "filing_date": max(fact["revenue_filed_date"], fact["earnings_filed_date"]),
                    "revenue_usd": str(revenue), "net_income_usd": str(income),
                    "net_margin_pct": str(margin),
                    "filing_accession": fact.get("source_filing_accession") or ""})
        findings.append(row)
    evidence_count = sum(x["status"] == "SEC_ANNUAL_EVIDENCE_AVAILABLE_NO_MARKET_RANK" for x in findings)
    # Usable comparisons exclude old annual filings even when same-accession
    # historical observations exist in the SEC payload.
    comparable_count = sum(x["status"] == "SEC_ANNUAL_EVIDENCE_AVAILABLE_NO_MARKET_RANK"
                           and x["comparison_status"] == "COMPARABLE_SAME_SEC_FILING"
                           for x in findings)
    stale_count = sum(x["status"] == "SEC_ANNUAL_STALE_REVIEW_NO_MARKET_RANK" for x in findings)
    return {"as_of": as_of.isoformat(), "mode": "SEC_REAL_ANNUAL_RESEARCH_COVERAGE_NOT_RANKING",
            "source_provider": "SEC EDGAR (official)",
            "catalog_source_url": SEC_TICKERS_URL,
            "catalog_sha256": catalog_meta["sha256"],
            "catalog_record_count": len(catalog),
            "selected_count": len(selected_symbols), "annual_evidence_count": evidence_count,
            "comparable_prior_year_count": comparable_count, "stale_annual_count": stale_count,
            "market_ranking_count": 0, "results": findings,
            "limitations": [
                "Current SEC tickers are not a survivorship-bias-free historical universe",
                "Annual US GAAP revenue and net income are not standardized valuations across industries",
                "No verified historical prices, split/dividend adjustment, sector, ISIN or oil exposure",
                "Net margin is a factual ratio, not a buy signal or forecast",
                "Prior-year growth requires same SEC filing accession and identical revenue/income concepts",
                "Non-comparable prior periods and stale annual filings are not forced into growth or rankings",
                "Past filings are filtered by filed date; future restatements are excluded",
                "No market ranking or trade-ready shortlist is produced",
            ]}


def write_sec_evidence(report: dict, output: Path):
    """Persist only public SEC-derived summary metrics and immutable source hashes."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = report["results"]
    fields = ["ticker", "cik", "name", "exchange", "venue", "status",
              "period_end", "filing_date", "revenue_usd", "net_income_usd",
              "net_margin_pct", "filing_accession", "source_url", "source_sha256",
              "comparison_status", "previous_period_end", "previous_revenue_usd",
              "previous_net_income_usd", "revenue_yoy_pct", "net_income_yoy_pct",
              "net_margin_change_pp", "annual_age_days"]
    if any(set(r) != set(fields) for r in rows):
        raise ValueError("Unexpected SEC report row schema")
    csv_stream = io.StringIO(newline="")
    writer = csv.DictWriter(csv_stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = csv_stream.getvalue().encode("utf-8")
    (output / "SEC_ANNUAL_RESEARCH.csv").write_bytes(data)
    (output / "SEC_ANNUAL_RESEARCH.json").write_text(
        json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# SEC EDGAR — first real-source research coverage", "",
             f"- As-of: **{report['as_of']}**",
             f"- SEC catalog entries: **{report['catalog_record_count']}**",
             f"- Selected: **{report['selected_count']}**; usable annual evidence: **{report['annual_evidence_count']}**",
             f"- Comparable annual growth pairs: **{report['comparable_prior_year_count']}**; stale filings: **{report['stale_annual_count']}**",
             "- Market ranking / buy shortlist: **NOT PRODUCED**", "",
             "| Ticker | Filing period | Revenue USD | Net income USD | Margin | Revenue YoY | Comparison | Quality |",
             "|---|---|---:|---:|---:|---:|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[c]).replace("|", "\\|") for c in
            ("ticker", "period_end", "revenue_usd", "net_income_usd", "net_margin_pct",
             "revenue_yoy_pct", "comparison_status", "status")) + " |")
    lines += ["", "**Limitations:**", *("- " + x for x in report["limitations"]), ""]
    (output / "SEC_ANNUAL_RESEARCH.md").write_text("\n".join(lines), encoding="utf-8")
    return {"output": str(output), "rows": len(rows), "annual_evidence_count": report["annual_evidence_count"],
            "csv_sha256": sha256_bytes(data)}


def collect_sec_pilot(symbols: list[str], as_of: date, cache: Path,
                      sec_contact: str, *, collector=collect, pause=time.sleep):
    """Explicit ≤25 SEC requests, 1.2s spacing, no retry or alternate providers."""
    if as_of != date.today():
        raise ValueError("Live SEC pilot requires today's as-of date (no backdated current universe)")
    if not isinstance(sec_contact, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", sec_contact):
        raise ValueError("SEC contact must be provided by environment or CLI")
    if not 1 <= len(symbols) <= MAX_SYMBOLS or any(not SYMBOL_RE.fullmatch(s) for s in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError("Invalid or repeated selection")
    catalog_meta = collector("SEC_TICKERS", "", cache, sec_contact=sec_contact)
    catalog = parse_sec_tickers(_read_source(catalog_meta, "SEC_TICKERS", SEC_TICKERS_URL, as_of))
    lookup = {}
    for r in catalog:
        if r["ticker"].upper() in symbols:
            lookup.setdefault(r["ticker"].upper(), []).append(r)
    facts = {}
    for symbol in symbols:
        matches = lookup.get(symbol, [])
        if len(matches) != 1 or matches[0]["venue"] == "UNMAPPED":
            continue
        cik = matches[0]["cik"]
        if cik in facts:
            continue
        pause(1.2)  # SEC fair-access well below 10 req/s
        facts[cik] = collector("SEC_COMPANYFACTS", cik, cache, sec_contact=sec_contact)
    return analyze_sec_evidence(catalog_meta, facts, symbols, as_of)
