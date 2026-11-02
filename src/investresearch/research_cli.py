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
    sec.add_argument('--as-of',default=date.today().isoformat())
    sec.add_argument('--live-confirm',action='store_true',help='Explicit authorization for SEC requests')
    sec.add_argument('--cache',type=Path,default=ROOT/'.cache/research')
    sec.add_argument('--output',type=Path,default=ROOT/'reports/generated/block_b/sec_pilot')
    sec.add_argument('--sec-contact',default=os.getenv('SEC_RESEARCH_CONTACT',''))
    c=sp.add_parser('collect',help='EXPLICIT NETWORK REQUEST, no paywall/provider fallback')
    c.add_argument('--provider',required=True,choices=['SEC_COMPANYFACTS','SEC_TICKERS','ECB_EUR_FX','YFINANCE_EOD_UNVERIFIED'])
    c.add_argument('--identifier',default='')
    c.add_argument('--cache',type=Path,default=ROOT/'.cache/research')
    c.add_argument('--sec-contact',default=os.getenv('SEC_RESEARCH_CONTACT',''))
    c.add_argument('--acknowledge-yahoo-terms',action='store_true',
                   help='Explicit opt-in for personal research under Yahoo Finance data terms')
    c.add_argument('--as-of',default=None,help='Historical cutoff YYYY-MM-DD; future snapshots prohibited')
    args=p.parse_args(argv)
    if args.command=='screen':
        if args.max_age_sessions not in (0,1,2,3,4,5):
            p.error('max-age-sessions must be between 0 and 5')
        settings=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
        result=screen(args.bundle,settings=settings,max_age_sessions=args.max_age_sessions)
        write_screening(result,args.output)
        print(f"Block B: {result['ranked_count']} / {result['universe_size']} ranked; mode {result['dataset_mode']}; output {args.output}")
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
        result=collect_sec_pilot(parse_symbols(args.symbols),date.fromisoformat(args.as_of),
            args.cache,args.sec_contact)
        summary=write_sec_evidence(result,args.output)
        print(f"SEC pilot: {summary['annual_evidence_count']} / {summary['rows']} annual profiles; no market ranking; saved {args.output}")
    elif args.command=='collect':
        meta=collect(args.provider,args.identifier,args.cache,
            sec_contact=args.sec_contact,
            acknowledge_yahoo_terms=args.acknowledge_yahoo_terms,as_of=args.as_of)
        # Never print SEC contact or download credentials; prints hash + safe source.
        print(json.dumps({k:meta[k] for k in ('provider','identifier','source_url','sha256','path','bytes')},indent=2))
    else:
        p.error('Unknown command')


if __name__=='__main__':main()
