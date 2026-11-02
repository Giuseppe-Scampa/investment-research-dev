"""Manual-only data layer + ranking, completely independent from broker execution."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .research_bundle import build_bundle
from .research_sources import collect
from .research_screen import screen,write_screening
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
    c=sp.add_parser('collect',help='EXPLICIT NETWORK REQUEST, no paywall/provider fallback')
    c.add_argument('--provider',required=True,choices=['SEC_COMPANYFACTS','ECB_EUR_FX','STOOQ_EOD_UNVERIFIED'])
    c.add_argument('--identifier',default='')
    c.add_argument('--cache',type=Path,default=ROOT/'.cache/research')
    c.add_argument('--sec-contact',default=os.getenv('SEC_RESEARCH_CONTACT',''))
    c.add_argument('--stooq-key',default=os.getenv('STOOQ_FREE_KEY',''))
    c.add_argument('--acknowledge-stooq-terms',action='store_true')
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
    elif args.command=='collect':
        meta=collect(args.provider,args.identifier,args.cache,
            sec_contact=args.sec_contact,stooq_key=args.stooq_key,
            acknowledge_stooq_terms=args.acknowledge_stooq_terms)
        # Never print API keys or SEC contact; descriptor redacts Stooq credential.
        print(json.dumps({k:meta[k] for k in ('provider','identifier','source_url','sha256','path','bytes')},indent=2))
    else:
        p.error('Unknown command')


if __name__=='__main__':main()
