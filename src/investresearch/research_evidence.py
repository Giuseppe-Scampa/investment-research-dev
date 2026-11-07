"""R-008/M4: source-bound fundamental, valuation, factor and macro evidence matrix.

Historical metrics come ONLY from the original screened bundle. Optional
public research is a dated, cited, *human-supplied* assertion, never a model
prediction or score uplift. Missing evidence is explicit per instrument.
Research source text is untrusted; the caller is responsible for rights and
independent primary-source fact checking. No API requests or brokerage data.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .research_bundle import SYNTHETIC, EXTERNAL
from .research_funnel import _eligible

VERSION="r008-evidence-matrix-v1"
INPUT="r008-dated-public-research-input-v1"
FIELDS=("valuation","macro","geopolitical","counter_thesis","factors")
SHA=re.compile(r"^[0-9a-f]{64}$")
SOURCE=re.compile(r"^[A-Z][A-Z0-9_-]{0,39}$")


def _canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,
        ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()


def _date(value):
    if not isinstance(value,str):
        raise ValueError("Research evidence publication date missing")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid evidence publication date") from None


def _bounded_string(value, name, max_len=1400):
    if not isinstance(value,str) or not 12<=len(value.strip())<=max_len:
        raise ValueError(f"{name}: bounded substantive explanatory text required")
    return value.strip()


def _validate_public(assertions, as_of, digest, eligible):
    if assertions is None:
        return {}
    if not isinstance(assertions,dict) or set(assertions)!={"schema_version","as_of","screening_sha256","research"}:
        raise ValueError("Manual research needs the exact public-only source schema")
    if assertions["schema_version"]!=INPUT or _date(assertions["as_of"])!=as_of:
        raise ValueError("Dated public research contract/as-of mismatch")
    if assertions["screening_sha256"]!=digest:
        raise ValueError("Manual research source must bind to original screening SHA")
    entries=assertions["research"]
    if not isinstance(entries,list) or len(entries)>min(5000,len(eligible)):
        raise ValueError("Research evidence count exceeds valid screened identities")
    seen=set()
    selected={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"id","notes","sources"}:
            raise ValueError("Research entry must have exact id, notes and source fields")
        uid=entry["id"]
        if not isinstance(uid,str) or uid not in eligible or uid in seen:
            raise ValueError("Research evidence unknown, excluded or repeated security identity")
        seen.add(uid)
        note=entry["notes"]
        if not isinstance(note,dict) or not note or not set(note).issubset(FIELDS):
            raise ValueError("Unknown/unbounded fundamental, macro, factor or valuation note")
        for key,content in note.items():
            _bounded_string(content,key)
        sources=entry["sources"]
        if not isinstance(sources,list) or not 1<=len(sources)<=8:
            raise ValueError("Research assertions require 1–8 dated public references")
        ids=set()
        for source in sources:
            if not isinstance(source,dict) or set(source)!={"source_id","url","published_date","sha256","supports"}:
                raise ValueError("Public research reference has invalid schema")
            sid=source["source_id"]
            if not isinstance(sid,str) or not SOURCE.fullmatch(sid) or sid in ids:
                raise ValueError("Invalid or duplicate cited source ID")
            ids.add(sid)
            url=source["url"]
            if not isinstance(url,str) or len(url)>1500:
                raise ValueError("Public source URL missing")
            u=urlsplit(url)
            if (u.scheme!="https" or not u.hostname or u.username or u.password
                    or u.fragment or u.port not in (None,443)
                    or u.hostname.lower() in ("localhost","127.0.0.1","::1")):
                raise ValueError("Research source must be a public HTTPS reference")
            if _date(source["published_date"])>as_of:
                raise ValueError("Research cites future/unpublished evidence")
            sha=source["sha256"]
            if sha is not None and (not isinstance(sha,str) or not SHA.fullmatch(sha)):
                raise ValueError("Source snapshot SHA must be lowercase SHA-256 or null")
            support=source["supports"]
            if (not isinstance(support,list) or not support
                    or len(support)>len(FIELDS)
                    or any(v not in note for v in support) or len(set(support))!=len(support)):
                raise ValueError("Evidence source does not declare supported note claims")
        supported={x for src in sources for x in src["supports"]}
        if supported!=set(note):
            raise ValueError("Every material research note requires at least one explicit source ID")
        selected[uid]={"notes":note,"sources":sources}
    return selected


def build_evidence(screening, manual=None):
    """Trace scored market rows and unscored factor/valuation/source gaps."""
    if not isinstance(screening,dict) or screening.get("schema_version")!=1:
        raise ValueError("Requires original Block B screening v1")
    mode=screening.get("dataset_mode")
    if mode not in (SYNTHETIC,EXTERNAL):
        raise ValueError("Unknown screening mode")
    when=_date(screening.get("as_of"))
    sha=screening.get("dataset_manifest_sha256")
    if not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise ValueError("Missing screened source manifest SHA")
    rows=screening.get("results")
    if (not isinstance(rows,list) or len(rows)>5000
            or screening.get("universe_size")!=len(rows)
            or screening.get("ranked_count")!=sum(
                x.get("market_score") is not None for x in rows if isinstance(x,dict))):
        raise ValueError("Screening count/score population mismatch")
    ids=set()
    good={}
    for r in rows:
        if not isinstance(r,dict) or not isinstance(r.get("id"),str) or r["id"] in ids:
            raise ValueError("Duplicate/invalid screen identity")
        ids.add(r["id"])
        if not _eligible(r,mode):
            good[r["id"]]=r
    digest=_canonical(screening)
    validated=_validate_public(manual,when,digest,good)
    outcome=[]
    for row in rows:
        meta=row.get("market_metrics") or {}
        fundamental=row.get("fundamental_metrics")
        if not isinstance(meta,dict):
            raise ValueError("Invalid market metrics")
        permitted={}
        for key in ("momentum_20","momentum_60","volatility_20",
                    "max_drawdown_60","avg_daily_turnover_eur_20","rsi_wilder_14"):
            value=meta.get(key)
            if type(value) in (int,float) and math.isfinite(value):
                permitted[key]=value
            else:
                permitted[key]=None
        note=validated.get(row["id"])
        field_notes=note["notes"] if note else {}
        documentary=row.get("documented_events_not_causal_predictions",[])
        if not isinstance(documentary,list) or len(documentary)>100:
            raise ValueError("Invalid bounded documented events")
        gaps=[]
        if row.get("market_score") is None:
            gaps.append("MISSING_QUALIFIED_61_SESSION_MARKET_METRICS")
        if row.get("asset_type")=="EQUITY" and not fundamental:
            gaps.append("MISSING_POINT_IN_TIME_EQUITY_FUNDAMENTALS")
        if not field_notes.get("valuation"):
            gaps.append("VALUATION_NOT_SOURCE_RECONCILED")
        if not field_notes.get("macro"):
            gaps.append("MACRO_RATE_INFLATION_FX_REGIME_NOT_SOURCE_RECONCILED")
        if not field_notes.get("geopolitical"):
            gaps.append("GEOPOLITICAL_AND_SECTOR_EXPOSURE_NOT_SOURCE_RECONCILED")
        if not field_notes.get("counter_thesis"):
            gaps.append("COUNTER_THESIS_NOT_INDEPENDENTLY_DOCUMENTED")
        if not field_notes.get("factors"):
            gaps.append("FACTOR_EXPOSURES_NOT_INDEPENDENTLY_DOCUMENTED")
        if not documentary:
            gaps.append("NO_DATED_CATALYST_EVENT_IN_SOURCE_BUNDLE")
        if note:
            gaps.append("MANUAL_SOURCE_CITATIONS_NOT_INDEPENDENTLY_FACT_CHECKED")
        outcome.append({
            "id":row["id"],"isin":row.get("isin",""),"venue":row.get("venue",""),
            "asset_type":row.get("asset_type",""),"sector":row.get("sector",""),
            "market_score":row.get("market_score"),
            "factor_proxies_historical_not_exposures":permitted,
            "equity_fundamentals_source_reported":fundamental,
            "event_count":len(documentary),
            "dated_events_not_predictive":documentary,
            "assertions":field_notes,
            "public_references":note["sources"] if note else [],
            "unresolved_gates":gaps,
            "stress_scenarios_conditional_pct":[-30,-15,0,15],
            "stress_note":"Fixed illustrative price shocks, NOT probabilities, profit forecasts or investment suitability.",
            "trade_ready":False,
        })
    return {
        "schema_version":VERSION,"as_of":when.isoformat(),
        "dataset_mode":mode,"dataset_manifest_sha256":sha,
        "screening_sha256":digest,
        "universe_count":len(rows),
        "market_ranked_count":screening["ranked_count"],
        "documented_fundamentals_count":sum(bool(r.get("fundamental_metrics")) for r in rows),
        "public_research_assertions_count":len(validated),
        "all_gaps":dict(sorted(Counter(g for r in outcome for g in r["unresolved_gates"]).items())),
        "items":outcome,
        "research_ready_for_trade":False,
        "valuation_macro_factor_status":"PARTIAL_MISSING_OR_HUMAN_ASSERTED_NOT_FACT_CHECKED",
        "limitations":[
            "Price indicators are historical factor PROXIES, not factor betas or expected returns.",
            "Annual net margin is not valuation, cash flow, capital structure or forward guidance.",
            "Manual observations are source-labelled assertions; citation IDs/URLs are NOT fact checked.",
            "Macro, geopolitical and event descriptions do not causally predict price moves.",
            "All conditional downside/upside percentages are fixed shocks, never forecast returns.",
            "No fiscal, broker, KID/PRIIPs or executable quote suitability is inferred.",
        ],
    }


def write_evidence(report, output, *, repo_root):
    target=Path(output).resolve()
    repo=Path(repo_root).resolve()
    if report["dataset_mode"]!=SYNTHETIC:
        if target.is_relative_to(repo) and not target.is_relative_to(repo/"data/private"):
            raise ValueError("External evidence must stay under private source directory")
    target.mkdir(parents=True,exist_ok=True)
    path=target/"RESEARCH_EVIDENCE.json"
    path.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Source-bound research evidence: not a recommendation","",
           f"As-of: {report['as_of']} / {report['dataset_mode']}",
           f"Universe: {report['universe_count']}, price ranked: {report['market_ranked_count']}",
           "","## Unresolved evidence gates"]
    lines.extend(f"- {html.escape(k)}: {v}" for k,v in report["all_gaps"].items())
    lines+=["","## Limitations"]+[f"- {html.escape(t)}" for t in report["limitations"]]
    (target/"RESEARCH_EVIDENCE.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return target
