"""Generate fake but structurally correct PUBLIC research/AI originals for crossrepo CI.

This emits NO market data, issuer facts, paid provider output or broker input.
Never publish generated artifacts as investment evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from investresearch.ai_counteranalysis import (
    counteranalysis_record,SCHEMA,PUBLIC_ONLY,
)
from investresearch.research_screen import screen
from investresearch.research_valuation import INPUT,_sha


def generate(*, bundle:Path, output:Path):
    out=output.resolve()
    if "synthetic_fixture" not in str(out) or out.exists():
        raise ValueError("Research-source sample must be a NEW synthetic_fixture directory")
    source=screen(bundle)
    if source["dataset_mode"]!="EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE":
        raise ValueError("This is a CI-only EXTERNAL code-path fixture")
    if len(source["results"])!=2 or not all(
            item["id"].startswith("TEST_ONLY_") and item["name"].startswith("NOT_MARKET_DATA_")
            for item in source["results"]):
        raise ValueError("Refuse to fabricate financial research for real securities")
    entries=[]
    for i,asset in enumerate(source["results"]):
        entries.append({
            "id":asset["id"],"currency":asset["currency"],
            "fiscal_period_end":"2026-06-30",
            "reference_date":"2026-10-31",
            "values":{
                "market_cap":str(1000000000+i*200000000),
                "net_income":str(120000000+i*10000000),
                "ebitda":str(260000000+i*25000000),
                "free_cash_flow":str(90000000+i*5000000),
                "net_debt":str(200000000+i*20000000),
            },
            "sources":[
                {
                    "url":"https://www.sec.gov/Archives/FICTITIOUS_CI_ONLY",
                    "published_date":"2026-09-30","sha256":None,
                    "document_kind":"ISSUER_INTERIM_FILING",
                },
                {
                    "url":"https://www.nasdaq.com/market-activity/FAKE_CI_ONLY",
                    "published_date":"2026-10-31","sha256":None,
                    "document_kind":"EXCHANGE_MARKET_CAP_REFERENCE",
                },
            ],
        })
    manual={
        "schema_version":INPUT,"as_of":source["as_of"],
        "screening_sha256":_sha(source),"records":entries,
    }
    spec={
        "schema_version":SCHEMA,"data_scope":PUBLIC_ONLY,
        "as_of":source["as_of"],
        "question":"What might refute a fictional technology sector growth hypothesis?",
        "sources":[{
            "source_id":"FAKE_ISSUER","url":"https://www.sec.gov/Archives/FICTITIOUS_CI_ONLY",
            "published_date":"2026-10-10",
            "excerpt":"Synthetic test-only margin uncertainty, not a real issuer filing.",
            "sha256":None,
        }],
    }
    answers=[
        {"summary":"Mock model one: margins are an unverified assumption.",
         "counterarguments":[{"claim":"Higher fictional costs may erode revenue margins.",
                              "source_ids":["FAKE_ISSUER"]}],
         "uncertainties":["The fictional source does not establish any tradable position."]},
        {"summary":"Mock model two: working-capital assumptions are untested.",
         "counterarguments":[{"claim":"Higher fictional costs may erode revenue margins.",
                              "source_ids":["FAKE_ISSUER"]},
                             {"claim":"Funding may be constrained in this fictional case.",
                              "source_ids":["FAKE_ISSUER"]}],
         "uncertainties":["No real historical forecast exists."]},
    ]
    ai=[
        counteranalysis_record(spec,provider,model,answer,local_call=False)
        for (provider,model),answer in zip(
            [("gemini","gemini-fake-ci"),("groq","groq-fake-ci")],answers)
    ]
    out.mkdir(parents=True)
    (out/"FAKE_ISSUER_VALUATION.json").write_text(
        json.dumps(manual,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for index,item in enumerate(ai,1):
        (out/f"FAKE_AI_ORIGINAL_{index}.json").write_text(
            json.dumps(item,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (out/"DO_NOT_TREAT_AS_MARKET_DATA.txt").write_text(
        "FAKE account-free unit test figures + fabricated AI statements. "
        "No real market prices, issuer filing, source rights, tax certification or trade.\n",
        encoding="utf-8")
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    generate(bundle=args.bundle,output=args.output)
    print("FAKE_PUBLIC_REVIEW_RECORDS_GENERATED=PASS (NEVER ORIGINAL MARKET FACTS)")


if __name__=="__main__":
    main()
