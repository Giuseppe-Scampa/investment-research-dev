"""CI-only synthetic SEC annual issuer links for private B→A contract smoke.

Original SEC CompanyFacts are NOT consulted. Output must stay in an ignored
synthetic_fixture/ directory and can never certify real annual issuer facts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from investresearch.cli import ROOT
from investresearch.research_screen import screen
from investresearch.research_fundamentals_link import LINK_SCHEMA,SEC_MODE,_digest


def generate(bundle,output):
    out=Path(output).resolve()
    if "synthetic_fixture" not in str(out) or out.exists():
        raise ValueError("Only fresh private synthetic_fixture test output allowed")
    orig=Path(bundle).resolve()
    if "synthetic_fixture" not in str(orig) or not (orig/"manifest.json").is_file():
        raise ValueError("Explicit existing fictional bundle required")
    settings=json.loads((ROOT/"config/settings.json").read_text(encoding="utf-8"))
    screening=screen(orig,settings=settings)
    rows=screening["results"]
    if len(rows)!=2 or not all(
            isinstance(row.get("id"),str) and row["id"].startswith("TEST_ONLY_")
            and row.get("name","").startswith("NOT_MARKET_DATA_")
            and row.get("asset_type")=="EQUITY"
            and row.get("venue")=="XNAS"
            for row in rows):
        raise ValueError("Only the exact two-security fictional B fixture is supported")
    as_of=screening["as_of"]
    links=[]
    findings=[]
    for n,row in enumerate(rows,1):
        cik=f"{n:010d}"
        ticker=f"FICTIONAL_{n}"
        links.append({
            "id":row["id"],"isin":row["isin"],
            "provider":"SEC_EDGAR","source_key":ticker,"source_cik":cik,
            "verification":"OPERATOR_ASSERTED_IDENTITY_NOT_CERTIFIED",
        })
        revenue=1000*n
        earnings=100*n
        findings.append({
            "ticker":ticker,"cik":cik,"venue":"XNAS",
            "status":"SEC_ANNUAL_EVIDENCE_AVAILABLE_NO_MARKET_RANK",
            "source_sha256":("b" if n==1 else "c")*64,
            "source_url":f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            "filing_date":"2026-04-01","period_end":"2025-12-31",
            "revenue_usd":str(revenue),"net_income_usd":str(earnings),
            "net_margin_pct":"10.00",
            "comparison_status":"COMPARABLE_SAME_SEC_FILING",
        })
    out.mkdir(parents=True)
    (out/"FICTIONAL_SOURCE_LINKS.json").write_text(json.dumps({
        "schema_version":LINK_SCHEMA,"as_of":as_of,
        "screening_sha256":_digest(screening),"links":links,
    },indent=2)+"\n")
    (out/"FICTIONAL_SEC_ANNUAL.json").write_text(json.dumps({
        "mode":SEC_MODE,"as_of":as_of,"results":findings,
    },indent=2)+"\n")
    (out/"READ_ME_SYNTHETIC_ONLY.txt").write_text(
        "No SEC issuer data collected; fake amounts, hashes, identities, "
        "CIKs and prices. Test-only and not evidence for investing.\n")
    print("FICTIONAL_CROSSREPO_ANNUAL_SOURCE_LINKS_GENERATED; NO REAL SEC FACTS")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    generate(a.bundle,a.output)


if __name__=="__main__":
    main()
