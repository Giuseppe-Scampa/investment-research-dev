"""Manual-only data layer + ranking, completely independent from broker execution."""
from __future__ import annotations
import argparse
import json
import os
from datetime import date, datetime, timezone
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
    tactical=sp.add_parser('tactical',
        help='Decision 2026: honest multi-asset tactical *research queue* from source-checked Block B screen')
    tactical.add_argument('--bundle',type=Path,required=True,help='Hashed research bundle, never authored scores')
    tactical.add_argument('--output',type=Path,required=True,help='External-source output is private-only in repo')
    tactical.add_argument('--fiscal-rules',type=Path,default=ROOT/'config/fiscal/rules_2026.json')
    tactical.add_argument('--max-age-sessions',type=int,default=1)
    ev=sp.add_parser('evidence',help='R-008 source-linked valuation/macro/factor/fundamental/gap ledger')
    ev.add_argument('--bundle',type=Path,required=True)
    ev.add_argument('--output',type=Path,required=True)
    ev.add_argument('--public-research',type=Path,default=None,help='Optional dated public-only research statements; never private wallet')
    ev.add_argument('--max-age-sessions',type=int,default=1)
    risk=sp.add_parser('risk',help='R-008 pairwise historical EUR EOD correlations from the SAME screened source bundle')
    risk.add_argument('--bundle',type=Path,required=True)
    risk.add_argument('--output',type=Path,required=True)
    risk.add_argument('--fiscal-rules',type=Path,default=ROOT/'config/fiscal/rules_2026.json')
    risk.add_argument('--max-age-sessions',type=int,default=1)
    batch=sp.add_parser('tiingo-personal-batch',
        help='Explicit 2–20 independently reviewed Tiingo US symbols per personal free-tier run; private only')
    batch.add_argument('--reviewed-manifest',type=Path,required=True,
                       help='Private r004-tiingo-free-bounded-batch-v1 manifest with 2 independently verified identity URLs per row')
    batch.add_argument('--acknowledge-personal-terms',action='store_true')
    batch.add_argument('--identity-reviewed',action='store_true')
    batch.add_argument('--output',type=Path,required=True,help='NEW ignored private source folder')
    merge=sp.add_parser('merge-free-tiingo',
        help='Offline combine 2–500 individually authorized private Tiingo one-symbol intake specs')
    merge.add_argument('--source-spec',type=Path,action='append',required=True,
                       help='Repeat for each existing BUNDLE_INPUT_SPEC.json')
    merge.add_argument('--output',type=Path,required=True,
                       help='NEW private combined JSON; bind ECB FX separately afterward')
    fxbind=sp.add_parser('bind-ecb-fx',
        help='Attach existing official ECB EUR/USD raw source to a local USD price spec; NO NETWORK')
    fxbind.add_argument('--spec',type=Path,required=True)
    fxbind.add_argument('--ecb-meta',type=Path,required=True)
    fxbind.add_argument('--output',type=Path,required=True)
    b=sp.add_parser('build',help='Normalize local raw provider snapshots to immutable bundle')
    b.add_argument('--spec',type=Path,required=True)
    b.add_argument('--output',type=Path,required=True)
    u=sp.add_parser('universe',help='Offline SEC candidate catalog; no implicit ranking')
    u.add_argument('--raw',type=Path,required=True)
    u.add_argument('--metadata',type=Path,required=True)
    u.add_argument('--as-of',required=True)
    u.add_argument('--limit',type=int,default=20000)
    u.add_argument('--output',type=Path,required=True)
    xetra=sp.add_parser('xetra-universe',help='Offline official Xetra T7 unranked multi-asset identity catalog; no prices')
    xetra.add_argument('--raw',type=Path,required=True,help='Manually downloaded official T7 CSV')
    xetra.add_argument('--metadata',type=Path,required=True,help='Verified source URL, SHA-256 and UTC retrieval time')
    xetra.add_argument('--as-of',required=True,help='Research date not earlier than file acquisition')
    xetra.add_argument('--output',type=Path,required=True,help='Local output; inside repo only data/private/')
    ecat=sp.add_parser('eodhd-xetra-catalog-collect',
        help='One explicit private EODHD Xetra symbol-list reference request; no prices')
    ecat.add_argument('--acknowledge-personal-terms',action='store_true')
    ecat.add_argument('--output',type=Path,required=True)
    cross=sp.add_parser('xetra-eodhd-crosswalk',
        help='Offline real Xetra+EODHD ISIN/venue/type source join; private identity coverage only')
    cross.add_argument('--xetra-raw',type=Path,required=True)
    cross.add_argument('--xetra-meta',type=Path,required=True)
    cross.add_argument('--eodhd-raw',type=Path,required=True)
    cross.add_argument('--eodhd-meta',type=Path,required=True)
    cross.add_argument('--as-of',required=True)
    cross.add_argument('--output',type=Path,required=True)
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
    ed=sp.add_parser('eodhd-personal-collect',
        help='Opt-in one EODHD Free/Personal EOD+split+dividend private local intake, 3 API calls')
    ed.add_argument('--symbol',required=True,help='Verified provider SYMBOL.EXCHANGE, not derived from ISIN')
    ed.add_argument('--isin',required=True,help='Independently reviewed 12-character security identity')
    ed.add_argument('--venue',required=True,choices=['XETR','XPAR','XNAS','XNYS'])
    ed.add_argument('--currency',required=True,choices=['EUR','USD'])
    ed.add_argument('--name',required=True,help='Reviewed instrument label')
    ed.add_argument('--asset-type',required=True,
        choices=['EQUITY','ETF_LEGAL_STATUS_UNVERIFIED','ETC','ETN'])
    ed.add_argument('--sector',required=True,help='Source-reviewed issuer sector/class, not guessed')
    ed.add_argument('--oil-exposure',required=True,
        choices=['none','indirect','material','primary','unknown'])
    ed.add_argument('--acknowledge-personal-terms',action='store_true',
                    help='Confirm individual noncommercial local data-use rights under EODHD terms')
    ed.add_argument('--identity-reviewed',action='store_true',
                    help='Confirm ISIN, venue and provider symbol checked against two independent references')
    ed.add_argument('--output',type=Path,required=True,
                    help='NEW ignored data/private directory or secure local external directory')
    ti=sp.add_parser('tiingo-personal-collect',
        help='Opt-in Tiingo Starter personal US EOD one-symbol source intake; local/private only')
    ti.add_argument('--symbol',required=True,help='Independently verified US provider ticker')
    ti.add_argument('--isin',required=True,help='Independently verified official ISIN')
    ti.add_argument('--venue',required=True,choices=['XNAS','XNYS'])
    ti.add_argument('--name',required=True,help='Reviewed issuer instrument name')
    ti.add_argument('--asset-type',required=True,choices=['EQUITY','ETF_LEGAL_STATUS_UNVERIFIED'])
    ti.add_argument('--sector',required=True,help='Issuer sector, not guessed from name')
    ti.add_argument('--oil-exposure',required=True,choices=['none','indirect','material','primary','unknown'])
    ti.add_argument('--acknowledge-personal-terms',action='store_true')
    ti.add_argument('--identity-reviewed',action='store_true')
    ti.add_argument('--output',type=Path,required=True)
    av=sp.add_parser('alpha-pilot',
        help='R-004: one opt-in Alpha Vantage raw DAILY symbol pilot, LOCAL ONLY / NO RANKING')
    av.add_argument('--symbol',required=True,help='Provider symbol; not ISIN or verified venue')
    av.add_argument('--venue',required=True,choices=['XNYS','XNAS','XMIL','XETR','XPAR'])
    av.add_argument('--as-of',default=datetime.now(timezone.utc).date().isoformat(),
                    help='Must be current UTC collection date, no backdated source claim')
    av.add_argument('--live-confirm',action='store_true',
                    help='Explicit authorization for exactly one live Alpha Vantage request')
    av.add_argument('--acknowledge-source-terms',action='store_true',
                    help='Confirm local diagnostic use, no external redistribution')
    av.add_argument('--output',type=Path,required=True,
                    help='Local ignored data/private directory or outside repository')
    td=sp.add_parser('twelve-pilot',
        help='R-004 opt-in Twelve Data Basic US one-symbol adjusted-request diagnostic; no ranking')
    td.add_argument('--symbol',required=True,help='Provider symbol, never inferred from ISIN')
    td.add_argument('--venue',required=True,choices=['XNYS','XNAS'])
    td.add_argument('--as-of',default=datetime.now(timezone.utc).date().isoformat())
    td.add_argument('--live-confirm',action='store_true')
    td.add_argument('--acknowledge-personal-terms',action='store_true',
                    help='Confirm personal internal-only noncommercial use; no raw redistribution')
    td.add_argument('--output',type=Path,required=True)
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
    # Operator cost policy: EODHD is NOT an operational dependency.
    # Historical EODHD adapters are kept only for regression tests.
    # Do not prompt for EODHD signup, use its API, or default to it.
    if args.command in ('eodhd-personal-collect','eodhd-xetra-catalog-collect',
                        'xetra-eodhd-crosswalk'):
        p.error('EODHD_DISABLED_NO_SUBSCRIPTION: use free Tiingo, official ECB/SEC or approved local files')
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
    elif args.command=='tactical':
        from .tactical_research import build_tactical, write_tactical
        from .tax_engine import FiscalRegistry
        if args.max_age_sessions not in (0,1,2,3,4,5):
            p.error('max-age-sessions must be between 0 and 5')
        settings=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
        report=screen(args.bundle,settings=settings,max_age_sessions=args.max_age_sessions)
        fiscal=FiscalRegistry.load(args.fiscal_rules)
        result=build_tactical(report,fiscal_registry=fiscal)
        write_tactical(result,args.output,repo_root=ROOT)
        print(f"Decision 2026 tactical: {result['status']}; "
              f"{result['instrument_count']} instruments, "
              f"{result['research_eligible_count']} research-eligible, "
              f"{len(result['research_priorities_by_type'])} priorities, "
              "0 final investments or orders")
    elif args.command=='evidence':
        from .research_evidence import build_evidence, write_evidence
        if args.max_age_sessions not in (0,1,2,3,4,5):
            p.error('max-age-sessions must be between 0 and 5')
        settings=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
        source=screen(args.bundle,settings=settings,max_age_sessions=args.max_age_sessions)
        manual=json.loads(args.public_research.read_text(encoding='utf-8')) if args.public_research else None
        result=build_evidence(source,manual=manual)
        write_evidence(result,args.output,repo_root=ROOT)
        print(f"R-008 research evidence: {result['universe_count']} instruments, "
              f"{result['public_research_assertions_count']} human-source statements, "
              "valuation/macro/AI not independently fact-checked, no investment signals")
    elif args.command=='risk':
        from .research_risk import analyze_risk, write_risk
        from .tactical_research import build_tactical
        from .tax_engine import FiscalRegistry
        if args.max_age_sessions not in (0,1,2,3,4,5):
            p.error('max-age-sessions must be between 0 and 5')
        settings=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
        screening=screen(args.bundle,settings=settings,max_age_sessions=args.max_age_sessions)
        tactical=build_tactical(screening,fiscal_registry=FiscalRegistry.load(args.fiscal_rules))
        report=analyze_risk(args.bundle,screening,tactical)
        write_risk(report,args.output,repo_root=ROOT)
        print(f"R-008 historical risk: {report['comparable_pairs']} comparable pairs / "
              f"{report['pairs_count']} investigated; {report['risk_scope']}; "
              "NO expected returns, orders or portfolio approval")
    elif args.command=='tiingo-personal-batch':
        from .research_tiingo_batch import collect_batch
        if not args.acknowledge_personal_terms or not args.identity_reviewed:
            p.error('Tiingo free batch requires personal noncommercial rights and two distinct identity references')
        audit=collect_batch(manifest_path=args.reviewed_manifest,
            output=args.output,repo_root=ROOT,api_token=os.getenv('TIINGO_API_TOKEN'),
            personal_rights_ack=True,identity_review_ack=True)
        print(f"Free Tiingo private batch: {audit['individual_source_count']} single-symbol source calls, "
              "no retry, ECB FX and price quality pending, no trade")
    elif args.command=='merge-free-tiingo':
        from .research_intake_merge import combine
        audit=combine(source_specs=args.source_spec,output=args.output,repo_root=ROOT)
        print(f"FREE TIINGO MULTI-ASSET MERGE: {audit['source_assets']} original price sources, "
              "ECB FX NOT YET BOUND; need explicit official ECB snapshot before ranking")
    elif args.command=='bind-ecb-fx':
        from .research_fx_bundle import bind_ecb_fx
        result=bind_ecb_fx(spec_path=args.spec,fx_meta_path=args.ecb_meta,
            output=args.output,repo_root=ROOT)
        print(f"ECB FX bound: {result['ecb_dates_available']} dated official rates; "
              f"USD instruments {result['usd_assets']}; "
              "source-only, needs session/price validation, no orders")
    elif args.command=='build':
        spec=json.loads(args.spec.read_text(encoding='utf-8'))
        if any(
            str(asset.get('prices_source',{}).get('provider','')).startswith('EODHD_')
            for asset in spec.get('assets',[]) if isinstance(asset,dict)
        ):
            p.error('EODHD_DISABLED_NO_SUBSCRIPTION: existing EODHD input not enabled in this workflow')
        result=build_bundle(spec,args.output)
        print(f"Bundle built: {len(result['assets'])} assets, source kinds {result['source_kinds']}")
    elif args.command=='universe':
        result=write_sec_candidates(args.raw,args.metadata,date.fromisoformat(args.as_of),args.output,limit=args.limit)
        print(f"SEC catalog: {result['candidate_count']} unranked candidates / {result['total_sec_records']} associations")
    elif args.command=='xetra-universe':
        from .research_xetra_universe import write_xetra_candidates
        result=write_xetra_candidates(args.raw,args.metadata,
            date.fromisoformat(args.as_of),args.output,repo_root=ROOT)
        print(f"Xetra discovery: {result['candidate_count']} source-identified instruments; "
              "unranked, no price or fiscal certification")
    elif args.command=='eodhd-xetra-catalog-collect':
        from .research_eodhd_catalog_collect import collect_catalog
        if not args.acknowledge_personal_terms:
            p.error('Official reference list requires personal data-use terms acknowledgement')
        report=collect_catalog(output=args.output,repo_root=ROOT,
            api_token=os.getenv('EODHD_API_TOKEN'),
            personal_rights_ack=True)
        print(f"EODHD Xetra private symbol catalog: "
              f"{report['usable_isin_records']} of {report['provider_records']} vendor rows "
              "(identifier coverage only, 0 ranking/quotes/orders)")
    elif args.command=='xetra-eodhd-crosswalk':
        from .research_eodhd_xetra_crosswalk import write_crosswalk
        report=write_crosswalk(args.xetra_raw,args.xetra_meta,
            args.eodhd_raw,args.eodhd_meta,date.fromisoformat(args.as_of),
            args.output,repo_root=ROOT)
        print(f"R-006 independent-source reference identity coverage: "
              f"{report['matched_count']}/{report['xetra_active_reference_count']} "
              "no historical price ranking, ISIN broker certification or trading")
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
    elif args.command=='tiingo-personal-collect':
        from .research_tiingo_personal_collect import collect_one
        if not args.acknowledge_personal_terms or not args.identity_reviewed:
            p.error('Tiingo personal intake requires verified rights scope and source identity')
        report=collect_one(
            symbol=args.symbol, isin=args.isin,venue=args.venue,
            instrument_name=args.name,asset_type=args.asset_type,
            sector=args.sector,oil_exposure=args.oil_exposure,
            output=args.output,repo_root=ROOT,
            api_token=os.getenv('TIINGO_API_TOKEN'),
            personal_rights_ack=True,identity_review_ack=True)
        print(f"Tiingo personal local intake: {report['source_sessions']} sessions; "
              f"split events {report['split_events_reported']}; "
              "0 market recommendations or orders")
    elif args.command=='eodhd-personal-collect':
        from .research_eodhd_personal_collect import collect_one
        if not args.acknowledge_personal_terms or not args.identity_reviewed:
            p.error('EODHD personal intake requires explicit licence-scope and ISIN mapping review')
        report=collect_one(symbol=args.symbol,isin=args.isin,venue=args.venue,
            currency=args.currency,instrument_name=args.name,
            asset_type=args.asset_type,sector=args.sector,
            oil_exposure=args.oil_exposure,output=args.output,repo_root=ROOT,
            api_token=os.getenv('EODHD_API_TOKEN'),
            personal_rights_ack=True,identity_review_ack=True)
        print(f"EODHD local personal source: {report['source_eod_sessions']} raw sessions, "
              f"{report['source_split_events']} split events, "
              f"{report['source_dividend_events']} dividend events; "
              "only private intake, no trading recommendation; 3 API calls")
    elif args.command=='alpha-pilot':
        from .research_alpha_pilot import run_pilot
        if not args.live_confirm or not args.acknowledge_source_terms:
            p.error('alpha-pilot requires --live-confirm and --acknowledge-source-terms')
        # Never accept a key on the CLI or in a public file.
        result=run_pilot(symbol=args.symbol,venue=args.venue,
              as_of=date.fromisoformat(args.as_of),output=args.output,
              repo_root=ROOT,api_key=os.getenv('ALPHAVANTAGE_API_KEY'),
              live_confirm=True,terms_confirm=True)
        print(f"Alpha Vantage local pilot: {result['symbol']} "
              f"{result['session_count']} RAW unverified sessions; "
              "no market score, no redistribution, no broker execution")
    elif args.command=='twelve-pilot':
        from .research_twelve_pilot import run_pilot
        if not args.live_confirm or not args.acknowledge_personal_terms:
            p.error('twelve-pilot requires --live-confirm and --acknowledge-personal-terms')
        meta=run_pilot(symbol=args.symbol,venue=args.venue,
            as_of=date.fromisoformat(args.as_of),output=args.output,
            repo_root=ROOT,api_key=os.getenv('TWELVE_DATA_API_KEY'),
            live_confirm=True,terms_confirm=True)
        print(f"Twelve Data Basic diagnostic: {meta['symbol']} "
              f"{meta['session_count']} bars, split adjustment requested "
              "not independently verified; NO RANKING/ORDERS")
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
