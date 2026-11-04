"""Manual-only data layer + ranking, completely independent from broker execution."""
from __future__ import annotations
import argparse
import json
import os
from datetime import date
from pathlib import Path
from .research_bundle import build_bundle
from .research_sources import collect
from .research_screen import screen,write_screening
from .research_universe import write_sec_candidates
from .cli import ROOT


def main(argv=None):
    p=argparse.ArgumentParser(description='Block B: opt-in free-source import and offline screening')
    sp=p.add_subparsers(dest='command',required=True)
    s=sp.add_parser('screen',help='Offline hash-verified screening from a dataset bundle')
    s.add_argument('--bundle',type=Path,default=ROOT/'data/research/demo')
    s.add_argument('--output',type=Path,default=ROOT/'reports/generated/block_b')
    s.add_argument('--max-age-sessions',type=int,default=1)
    funnel=sp.add_parser('funnel',help='R-007 offline funnel: broad screened universe to evidence review queue')
    funnel.add_argument('--bundle',type=Path,required=True,help='Source checked Block B bundle, not an arbitrary rank CSV')
    funnel.add_argument('--output',type=Path,required=True,help='External data inside repo only in data/private/')
    funnel.add_argument('--policy',type=Path,help='Optional R-007 validated limits JSON')
    funnel.add_argument('--diligence',type=Path,help='Optional manual public issuer due-diligence JSON')
    funnel.add_argument('--max-age-sessions',type=int,default=1)
    b=sp.add_parser('build',help='Normalize local raw provider snapshots to immutable bundle')
    b.add_argument('--spec',type=Path,required=True)
    b.add_argument('--output',type=Path,required=True)
    u=sp.add_parser('universe',help='Offline SEC candidate catalog; no implicit ranking')
    u.add_argument('--raw',type=Path,required=True)
    u.add_argument('--metadata',type=Path,required=True)
    u.add_argument('--as-of',required=True)
    u.add_argument('--limit',type=int,default=20000)
    u.add_argument('--output',type=Path,required=True)
    sec=sp.add_parser('sec-pilot',help='One manual SEC-only current-catalog/annual-evidence pilot, no market ranking')
    sec.add_argument('--symbols',default='AAPL,MSFT,NVDA,AMZN')
    sec.add_argument('--cohort',type=Path,help='JSON file with symbols list (max 24); overrides --symbols')
    sec.add_argument('--as-of',default=date.today().isoformat())
    sec.add_argument('--live-confirm',action='store_true',help='Explicit authorization for SEC requests')
    sec.add_argument('--cache',type=Path,default=ROOT/'.cache/research')
    sec.add_argument('--output',type=Path,default=ROOT/'reports/generated/block_b/sec_pilot')
    sec.add_argument('--sec-contact',default=os.getenv('SEC_RESEARCH_CONTACT',''))
    eu=sp.add_parser('eu-filings',help='Offline ESEF/PDF report evidence inventory; no XBRL financial scoring')
    eu.add_argument('--spec',type=Path,required=True)
    eu.add_argument('--root',type=Path,help='Local document root; defaults to the spec directory')
    eu.add_argument('--output',type=Path,required=True)
    eu.add_argument('--extract-ifrs',action='store_true', help='Opt-in conservative Inline XBRL candidate extraction; no verified accounting/ranking')
    c=sp.add_parser('collect',help='EXPLICIT NETWORK REQUEST, no paywall/provider fallback')
    c.add_argument('--provider',required=True,choices=['SEC_COMPANYFACTS','SEC_TICKERS','ECB_EUR_FX','YFINANCE_EOD_UNVERIFIED'])
    c.add_argument('--identifier',default='')
    c.add_argument('--cache',type=Path,default=ROOT/'.cache/research')
    c.add_argument('--sec-contact',default=os.getenv('SEC_RESEARCH_CONTACT',''))
    c.add_argument('--acknowledge-yahoo-terms',action='store_true',
                   help='Explicit opt-in for personal research under Yahoo Finance data terms')
    c.add_argument('--as-of',default=None,help='Historical cutoff YYYY-MM-DD; future snapshots prohibited')
    ai=sp.add_parser('ai-countercheck',
        help='R-009: optional public-only AI counteranalysis; local Ollama or offline imported provider response')
    ai.add_argument('--spec',type=Path,required=True,help='Public issuer research only; no bank/personal data')
    ai.add_argument('--provider',choices=['ollama-local','gemini','groq','openrouter'],required=True)
    ai.add_argument('--model',required=True,help='Explicit model identifier; no default or paid API')
    ai.add_argument('--response-json',type=Path,help='Offline JSON response produced elsewhere, no API calls')
    ai.add_argument('--invoke-local-ollama',action='store_true',
                    help='Explicit opt-in: localhost:11434 only; no remote fallback')
    ai.add_argument('--acknowledge-public-only',action='store_true',
                    help='Confirm all quoted content is public issuer research, never broker data')
    ai.add_argument('--output',type=Path,required=True,help='Private/ignored local folder for generated artifacts')
    args=p.parse_args(argv)
    if args.command=='screen':
        if args.max_age_sessions not in (0,1,2,3,4,5):
            p.error('max-age-sessions must be between 0 and 5')
        settings=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
        result=screen(args.bundle,settings=settings,max_age_sessions=args.max_age_sessions)
        write_screening(result,args.output)
        print(f"Block B: {result['ranked_count']} / {result['universe_size']} ranked; mode {result['dataset_mode']}; output {args.output}")
    elif args.command=='funnel':
        from .research_funnel import build_funnel, write_funnel
        if args.max_age_sessions not in (0,1,2,3,4,5):
            p.error('max-age-sessions must be between 0 and 5')
        settings=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
        report=screen(args.bundle,settings=settings,max_age_sessions=args.max_age_sessions)
        policy=json.loads(args.policy.read_text(encoding='utf-8')) if args.policy else None
        diligence=json.loads(args.diligence.read_text(encoding='utf-8')) if args.diligence else None
        result=build_funnel(report,policy=policy,diligence=diligence)
        write_funnel(result,args.output,repo_root=ROOT)
        print(f"R-007 funnel: {result['status']} | "
              f"{result['input_universe_count']} in universe; "
              f"{len(result['stage_1_pool'])} research / "
              f"{len(result['stage_2_deep_dive'])} deep-dive / "
              f"{len(result['stage_3_provisional_finalists'])} provisional. "
              "NOT trade-ready.")
    elif args.command=='build':
        spec=json.loads(args.spec.read_text(encoding='utf-8'))
        result=build_bundle(spec,args.output)
        print(f"Bundle built: {len(result['assets'])} assets, source kinds {result['source_kinds']}")
    elif args.command=='universe':
        result=write_sec_candidates(args.raw,args.metadata,date.fromisoformat(args.as_of),args.output,limit=args.limit)
        print(f"SEC catalog: {result['candidate_count']} unranked candidates / {result['total_sec_records']} associations")
    elif args.command=='sec-pilot':
        from .research_sec_pilot import parse_symbols, collect_sec_pilot, write_sec_evidence
        if not args.live_confirm:
            p.error('sec-pilot requires --live-confirm; never fetch implicitly')
        if args.cohort:
            group=json.loads(args.cohort.read_text(encoding='utf-8'))
            symbols=group.get('symbols')
            if not isinstance(symbols,list) or not all(isinstance(s,str) for s in symbols):
                p.error('SEC cohort must have an array of ticker strings in symbols')
            chosen=parse_symbols(','.join(symbols))
        else:
            chosen=parse_symbols(args.symbols)
        result=collect_sec_pilot(chosen,date.fromisoformat(args.as_of),
            args.cache,args.sec_contact)
        summary=write_sec_evidence(result,args.output)
        print(f"SEC pilot: {summary['annual_evidence_count']} / {summary['rows']} annual profiles; no market ranking; saved {args.output}")
    elif args.command=='eu-filings':
        from .research_eu_filings import audit_eu_reports, write_eu_report
        spec=json.loads(args.spec.read_text(encoding='utf-8'))
        report=audit_eu_reports(spec,args.root or args.spec.parent,extract_ifrs=args.extract_ifrs)
        write_eu_report(report,args.output)
        print(f"EU report inventory: {report['document_count']} files, {report['ixbrl_candidate_count']} provisional IFRS facts, 0 verified or ranked; {args.output}")
    elif args.command=='collect':
        meta=collect(args.provider,args.identifier,args.cache,
            sec_contact=args.sec_contact,
            acknowledge_yahoo_terms=args.acknowledge_yahoo_terms,as_of=args.as_of)
        # Never print SEC contact or download credentials; prints hash + safe source.
        print(json.dumps({k:meta[k] for k in ('provider','identifier','source_url','sha256','path','bytes')},indent=2))
    elif args.command=='ai-countercheck':
        from .ai_counteranalysis import (
            MAX_RESPONSE_BYTES, validate_public_spec, parse_response,
            invoke_local_ollama, counteranalysis_record, write_counteranalysis)
        if not args.acknowledge_public_only:
            p.error('ai-countercheck requires --acknowledge-public-only')
        if bool(args.response_json)==bool(args.invoke_local_ollama):
            p.error('Choose exactly one: --response-json OR --invoke-local-ollama')
        if args.invoke_local_ollama and args.provider!='ollama-local':
            p.error('Only local Ollama may be invoked; other providers are offline import only')
        spec=validate_public_spec(json.loads(args.spec.read_text(encoding='utf-8')))
        if args.invoke_local_ollama:
            answer=invoke_local_ollama(spec,args.model,explicitly_authorized=True)
        else:
            if args.response_json.stat().st_size>MAX_RESPONSE_BYTES:
                p.error('Offline model response exceeds size limit')
            answer=parse_response(spec,args.provider,args.model,
                 args.response_json.read_text(encoding='utf-8'))
        record=counteranalysis_record(spec,args.provider,args.model,answer,
                local_call=args.invoke_local_ollama)
        write_counteranalysis(record,args.output,repo_root=ROOT)
        print('R-009: unverified public-source counteranalysis saved locally; '
              'citation IDs are not fact-checked; no trade authorization')
    else:
        p.error('Unknown command')


if __name__=='__main__':main()
