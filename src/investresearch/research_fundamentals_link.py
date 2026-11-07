"""R-008: link dated SEC/ESEF annual evidence to B screening by explicit identity.

No ticker-to-ISIN invention, raw remote fetching, filling missing issuer facts,
valuation multiple without market cap, screening uplift or trade instructions.
Both the linkage and the original SEC/issuer claims remain unverified.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .research_bundle import SYNTHETIC, EXTERNAL
from .quality import valid_isin

VERSION = "r008-annual-fundamental-evidence-link-v1"
LINK_SCHEMA = "r008-annual-source-identity-links-v1"
SEC_MODE = "SEC_REAL_ANNUAL_RESEARCH_COVERAGE_NOT_RANKING"
EU_MODE = "EU_ANNUAL_REPORT_EVIDENCE_NOT_FINANCIAL_FACTS_OR_RANKING"
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_ROWS = 5000
MAX_LINKS = 100


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _date(value, cutoff):
    if not isinstance(value, str):
        raise ValueError("Missing original fundamental evidence date")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid original fundamental evidence date") from None
    if day > cutoff:
        raise ValueError("Future publication/filing would cause lookahead")
    return day


def _amount(value, *, positive=False):
    if isinstance(value,bool):
        raise ValueError("Malformed SEC evidence number")
    try:
        amt = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Malformed SEC evidence number") from None
    if not amt.is_finite() or abs(amt)>Decimal("1e16") or (positive and amt<=0):
        raise ValueError("SEC original metric invalid or too large")
    return amt


def _sources(sec, eu, cutoff):
    sources={}
    for provider,report,mode in (("SEC_EDGAR",sec,SEC_MODE),("EU_ESEF",eu,EU_MODE)):
        if report is None:
            continue
        if (not isinstance(report,dict) or report.get("mode")!=mode or
                _date(report.get("as_of"),cutoff)!=cutoff):
            raise ValueError("Original annual-fundamental source report mode/as_of mismatch")
        rows=report.get("results")
        if not isinstance(rows,list) or len(rows)>MAX_ROWS:
            raise ValueError("Malformed or oversize annual report")
        index={}
        for row in rows:
            if not isinstance(row,dict):
                raise ValueError("Malformed annual source row")
            if provider=="SEC_EDGAR":
                key=(row.get("ticker"),row.get("cik"))
            else:
                key=(row.get("id"),"")
            if not all(isinstance(v,str) for v in key) or key in index:
                raise ValueError("Ambiguous or duplicate annual-source identity")
            index[key]=row
        sources[provider]=index
    return sources


def build_fundamental_links(screening, links, *, sec_report=None, eu_report=None):
    """Non-authoritative source evidence overlay; never changes original rank."""
    if not isinstance(screening,dict) or screening.get("schema_version")!=1:
        raise ValueError("Original source-bound B screening required")
    rows=screening.get("results")
    if (not isinstance(rows,list) or len(rows)>MAX_ROWS
            or len(rows)!=screening.get("universe_size")
            or screening.get("dataset_mode") not in (SYNTHETIC,EXTERNAL)):
        raise ValueError("Invalid screening universe for issuer evidence")
    original_sha=_digest(screening)
    cutoff=_date(screening.get("as_of"),date.max)
    if (not isinstance(links,dict) or set(links)!=
            {"schema_version","as_of","screening_sha256","links"}
            or links["schema_version"]!=LINK_SCHEMA
            or _date(links["as_of"],cutoff)!=cutoff
            or links["screening_sha256"]!=original_sha
            or not isinstance(links["links"],list)
            or len(links["links"])>MAX_LINKS):
        raise ValueError("Original issuer links not bound to exact screening and date")
    indexed={row["id"]:row for row in rows}
    if len(indexed)!=len(rows):
        raise ValueError("Repeated source screening identity")
    sources=_sources(sec_report,eu_report,cutoff)
    outputs={}
    utilized=set()
    for link in links["links"]:
        if (not isinstance(link,dict) or set(link)!={
                "id","isin","provider","source_key","source_cik","verification"}
                or link.get("verification")!="OPERATOR_ASSERTED_IDENTITY_NOT_CERTIFIED"):
            raise ValueError("Annual source identity requires exact unverified mapping schema")
        uid=link.get("id")
        row=indexed.get(uid)
        if (row is None or uid in outputs or row.get("asset_type")!="EQUITY"
                or not isinstance(link["isin"],str) or not valid_isin(link["isin"])
                or row.get("isin")!=link["isin"]):
            raise ValueError("Unverified/mismatched or duplicate issuer ISIN identity")
        provider=link["provider"]
        key=(link["source_key"],link["source_cik"])
        if (provider not in sources or
                not all(isinstance(v,str) for v in key) or key in utilized):
            raise ValueError("Ambiguous or unavailable annual source mapping")
        if provider=="EU_ESEF" and key[1]!="":
            raise ValueError("ESEF linkage must not invent a SEC CIK")
        original=sources[provider].get(key)
        if original is None:
            raise ValueError("Source issuer/ticker/CIK not present in original report")
        utilized.add(key)
        if provider=="SEC_EDGAR":
            if (original.get("status")!="SEC_ANNUAL_EVIDENCE_AVAILABLE_NO_MARKET_RANK"
                    or original.get("venue")!=row.get("venue")
                    or not isinstance(original.get("source_sha256"),str)
                    or not SHA.fullmatch(original["source_sha256"])
                    or not isinstance(original.get("source_url"),str)
                    or not original["source_url"].startswith("https://data.sec.gov/api/xbrl/companyfacts/")):
                raise ValueError("SEC identity, venue, source or freshness not reviewable")
            published=_date(original.get("filing_date"),cutoff)
            period=_date(original.get("period_end"),published)
            revenue=_amount(original.get("revenue_usd"),positive=True)
            income=_amount(original.get("net_income_usd"))
            documented_margin=(income/revenue*100).quantize(Decimal("0.01"))
            if _amount(original.get("net_margin_pct"))!=documented_margin:
                raise ValueError("SEC accounting margin does not reconcile to cited values")
            outputs[uid]={
                "id":uid,"isin":row["isin"],"provider":provider,
                "status":"SEC_ANNUAL_FACTS_CROSSWALK_OPERATOR_ASSERTED_NOT_CERTIFIED",
                "source_key":link["source_key"],"source_cik":link["source_cik"],
                "source_sha256":original["source_sha256"],
                "source_url":original["source_url"],
                "published_date":published.isoformat(),
                "fiscal_period_end":period.isoformat(),
                "revenue_usd":str(revenue),"net_income_usd":str(income),
                "net_margin_pct":str(documented_margin),
                "annual_comparison_status":original.get("comparison_status"),
                "issuer_facts_independently_authenticated":False,
                "identity_link_certified":False,"trade_ready":False,
            }
        else:
            if (original.get("isin")!=row["isin"]
                    or not isinstance(original.get("document_sha256"),str)
                    or not SHA.fullmatch(original["document_sha256"])
                    or original.get("format") not in ("ESEF_XHTML","ESEF_ZIP","ANNUAL_PDF")):
                raise ValueError("Original ESEF/PDF issuer identity or checksum missing")
            published=_date(original.get("published_date_declared"),cutoff)
            period=_date(original.get("fiscal_year_end"),published)
            ix=original.get("ixbrl") or {}
            n=ix.get("candidate_count",0)
            if type(n) is not int or not 0<=n<=10000:
                raise ValueError("Invalid ESEF candidate concept count")
            outputs[uid]={
                "id":uid,"isin":row["isin"],"provider":provider,
                "status":"ESEF_DOCUMENT_AND_IFRS_CANDIDATES_NOT_FACT_VERIFIED",
                "source_key":link["source_key"],"source_cik":"",
                "source_sha256":original["document_sha256"],
                "source_url":original.get("source_url_declared",""),
                "published_date":published.isoformat(),
                "fiscal_period_end":period.isoformat(),
                "ixbrl_candidate_count":n,
                "issuer_facts_independently_authenticated":False,
                "identity_link_certified":False,"trade_ready":False,
            }
    entries=[]
    for row in rows:
        entries.append(outputs.get(row["id"],{
            "id":row["id"],"isin":row.get("isin",""),"provider":None,
            "status":"NO_EXPLICIT_ORIGINAL_ANNUAL_SOURCE_LINK",
            "source_key":None,"source_cik":None,"source_sha256":None,
            "source_url":None,"published_date":None,"fiscal_period_end":None,
            "issuer_facts_independently_authenticated":False,
            "identity_link_certified":False,"trade_ready":False,
        }))
    return {
        "schema_version":VERSION,"as_of":cutoff.isoformat(),
        "dataset_mode":screening["dataset_mode"],
        "dataset_manifest_sha256":screening["dataset_manifest_sha256"],
        "screening_sha256":original_sha,
        "universe_count":len(entries),
        "source_linked_count":len(outputs),
        "sec_source_linked_count":sum(x["provider"]=="SEC_EDGAR" for x in outputs.values()),
        "eu_source_linked_count":sum(x["provider"]=="EU_ESEF" for x in outputs.values()),
        "entries":entries,
        "rank_or_tax_effect":False,"trade_ready":False,
        "fundamental_facts_certified":False,"links_independently_verified":False,
        "limitations":[
            "SEC tickers do not establish an ISIN; CIK/ticker/ISIN is an operator declaration.",
            "ESEF issuer ISIN and publication date were supplied with the original document, not independently authenticated.",
            "iXBRL candidates and SEC reported metrics are not audited financial statement facts by this engine.",
            "No shares outstanding/market capitalization, no valuation multiple and no portfolio forecast.",
            "Missing or mismatched source identities cannot become research or trading ranks.",
        ],
    }


def write_fundamental_links(report, output, *, repo_root):
    target=Path(output).resolve()
    root=Path(repo_root).resolve()
    if report["dataset_mode"]!=SYNTHETIC and target.is_relative_to(root) and not target.is_relative_to(root/"data/private"):
        raise ValueError("External fundamental evidence must remain under private local data")
    target.mkdir(parents=True,exist_ok=True)
    (target/"RESEARCH_ANNUAL_FACTS.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    return target
