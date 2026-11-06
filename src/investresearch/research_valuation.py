"""M4/R-008: conservative source-dated equity valuation ratio calculator.

No scraped prices, provider API, share-price forecasts or invented issuer facts.
Numeric input is explicitly PUBLIC issuer/market evidence supplied by an
operator; original facts, issuance/currency basis and licence are NOT independently
verified by the engine. Sector comparability is only descriptive; these ratios
never add points to market ranking or mark an instrument trade-ready.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from .research_bundle import EXTERNAL,SYNTHETIC

VERSION="r008-dated-equity-valuation-v1"
INPUT="r008-public-dated-financial-values-v1"
SHA=re.compile(r"^[0-9a-f]{64}$")
KEYS=("market_cap","net_income","ebitda","free_cash_flow","net_debt")


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def _number(value, *, positive=False):
    if isinstance(value,bool) or value is None:
        raise ValueError("Explicit finite numeric financial input required")
    try:
        d=Decimal(str(value))
    except (ValueError,InvalidOperation,TypeError):
        raise ValueError("Malformed decimal financial source") from None
    if not d.is_finite() or (positive and d<=0):
        raise ValueError("Invalid numeric source range")
    if abs(d)>Decimal("1e16"):
        raise ValueError("Unsupported financial amount magnitude or units")
    return d


def _day(raw):
    if not isinstance(raw,str):
        raise ValueError("Source financial date missing")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError("Malformed financial date") from None


def _source(src, cutoff):
    if not isinstance(src,dict) or set(src)!={"url","published_date","sha256","document_kind"}:
        raise ValueError("Valuation issuer/market source requires exact metadata")
    url=src["url"]
    if not isinstance(url,str) or len(url)>1500:
        raise ValueError("Invalid valuation source URL")
    p=urlsplit(url)
    if (p.scheme!="https" or not p.hostname or p.username or p.password or p.fragment
            or p.port not in (None,443)
            or p.hostname.lower() in ("localhost","127.0.0.1","::1")):
        raise ValueError("Valuation source is not a public HTTPS original reference")
    if _day(src["published_date"])>cutoff:
        raise ValueError("Valuation source not yet published as-of research date")
    digest=src["sha256"]
    if digest is not None and (not isinstance(digest,str) or not SHA.fullmatch(digest)):
        raise ValueError("Original source SHA must be a lowercase SHA256 or null")
    if src["document_kind"] not in ("ISSUER_ANNUAL_FILING","ISSUER_INTERIM_FILING",
                                    "EXCHANGE_MARKET_CAP_REFERENCE","COMPANY_RELEASE"):
        raise ValueError("Unsupported source basis; never guess valuation facts")


def _ratio(n,d):
    return (str((n/d).quantize(Decimal(".000001"))) if d>0 else None)


def build_valuation(screening, financial_values=None):
    if not isinstance(screening,dict) or screening.get("schema_version")!=1:
        raise ValueError("Source-bound original B screening v1 required")
    rows=screening.get("results")
    if not isinstance(rows,list) or len(rows)!=screening.get("universe_size") or len(rows)>5000:
        raise ValueError("Invalid source universe count for valuation")
    mode=screening.get("dataset_mode")
    if mode not in (EXTERNAL,SYNTHETIC):
        raise ValueError("Invalid valuation data mode")
    cutoff=_day(screening.get("as_of"))
    ref_sha=screening.get("dataset_manifest_sha256")
    if not isinstance(ref_sha,str) or not SHA.fullmatch(ref_sha):
        raise ValueError("Original manifest not hash-bound")
    original_sha=_sha(screening)
    indexed={r["id"]:r for r in rows}
    if len(indexed)!=len(rows):
        raise ValueError("Duplicate screened issuer identity")
    inputs={}
    if financial_values is not None:
        if (not isinstance(financial_values,dict) or set(financial_values)!={
                "schema_version","as_of","screening_sha256","records"}
                or financial_values["schema_version"]!=INPUT
                or _day(financial_values["as_of"])!=cutoff
                or financial_values["screening_sha256"]!=original_sha):
            raise ValueError("Dated valuation inputs do not bind original screening")
        original=financial_values["records"]
        if not isinstance(original,list) or len(original)>len(rows):
            raise ValueError("Too many manual equity valuations")
        for item in original:
            if not isinstance(item,dict) or set(item)!={
                    "id","currency","fiscal_period_end","reference_date",
                    "values","sources"}:
                raise ValueError("Unexpected valuation source fields")
            uid=item["id"]
            row=indexed.get(uid)
            if (row is None or uid in inputs or row.get("asset_type")!="EQUITY"
                    or row.get("currency")!=item["currency"]
                    or row.get("market_score") is None):
                raise ValueError("Valuation is not tied to a source-ranked comparable equity")
            if _day(item["fiscal_period_end"])>_day(item["reference_date"]) or _day(item["reference_date"])>cutoff:
                raise ValueError("Future or inconsistent issuer metric reference date")
            values=item["values"]
            if not isinstance(values,dict) or set(values)!=set(KEYS):
                raise ValueError("Financial valuation requires exactly documented values/units")
            decimals={k:_number(v,positive=(k=="market_cap")) for k,v in values.items()}
            refs=item["sources"]
            if not isinstance(refs,list) or not 2<=len(refs)<=5:
                raise ValueError("Valuation uses independently cited issuer and market cap sources")
            for ref in refs:
                _source(ref,cutoff)
            if not any(s["document_kind"] in ("ISSUER_ANNUAL_FILING","ISSUER_INTERIM_FILING") for s in refs):
                raise ValueError("Original issuer statement must be present")
            if not any(s["document_kind"]=="EXCHANGE_MARKET_CAP_REFERENCE" for s in refs):
                raise ValueError("Original market cap/valuation price reference required")
            inputs[uid]={"values":decimals,"sources":refs,
                         "period":item["fiscal_period_end"],
                         "reference_date":item["reference_date"]}
    output=[]
    for row in rows:
        item=inputs.get(row["id"])
        if item:
            m=item["values"]
            enterprise=m["market_cap"]+m["net_debt"]
            ratios={
                "historical_earnings_yield":_ratio(m["net_income"],m["market_cap"]),
                "historical_free_cash_flow_yield":_ratio(m["free_cash_flow"],m["market_cap"]),
                "historical_ev_to_ebitda":_ratio(enterprise,m["ebitda"]) if enterprise>0 else None,
                "historical_market_cap_to_net_income":_ratio(m["market_cap"],m["net_income"]),
                "net_debt_to_ebitda":_ratio(m["net_debt"],m["ebitda"]),
            }
            serialized={k:str(v) for k,v in m.items()}
            status="SOURCE_ASSERTED_FINANCIAL_RATIOS_NOT_INDEPENDENTLY_VERIFIED"
            refs=item["sources"]
        else:
            ratios={k:None for k in ("historical_earnings_yield",
                "historical_free_cash_flow_yield","historical_ev_to_ebitda",
                "historical_market_cap_to_net_income","net_debt_to_ebitda")}
            serialized={}
            status=("NON_EQUITY_NO_COMPARABLE_VALUATION" if
                    row.get("asset_type")!="EQUITY" else
                    "MISSING_PRIMARY_SOURCE_VALUATION_INPUT")
            refs=[]
        output.append({
            "id":row["id"],"isin":row.get("isin",""),
            "asset_type":row.get("asset_type"),"currency":row.get("currency"),
            "status":status,"source_values":serialized,
            "ratios":ratios,"original_source_references":refs,
            "issuer_fiscal_period_end":item["period"] if item else None,
            "market_cap_reference_date":item["reference_date"] if item else None,
            "cross_currency_multiples_compared":False,
            "independent_source_claim_verification":False,
            "investment_or_issuer_recommendation":False,"trade_ready":False,
        })
    return {
        "schema_version":VERSION,"as_of":cutoff.isoformat(),
        "dataset_mode":mode,"dataset_manifest_sha256":ref_sha,
        "screening_sha256":original_sha,
        "universe_count":len(rows),"source_asserted_valuations_count":len(inputs),
        "items":output,"rank_or_tax_effect":False,"trade_ready":False,
        "limitations":[
            "Financial amounts are source-supplied same-currency annual/interim values; units and consolidation scope require human review.",
            "Market cap date and statement period may differ; historical multiples are not forward valuation or price targets.",
            "Missing or negative earnings/EBITDA give N/A ratios, not artificially low/high scores.",
            "Non-equity ETC/ETN/ETF/structured products need separate contractual payoff and NAV rules.",
            "Issuer reference URLs and SHA assertions do not independently authenticate issuer, licence or financial values.",
        ],
    }


def write_valuation(report,outdir,*,repo_root):
    out=Path(outdir).resolve()
    root=Path(repo_root).resolve()
    if report["dataset_mode"]!=SYNTHETIC and out.is_relative_to(root) and not out.is_relative_to(root/"data/private"):
        raise ValueError("External valuation reports are PRIVATE-only inside repository")
    out.mkdir(parents=True,exist_ok=True)
    (out/"RESEARCH_VALUATION.json").write_text(
        json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    return out
