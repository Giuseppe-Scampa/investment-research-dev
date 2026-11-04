"""Evidence-first, non-predictive market screening (Block B / M3+M4).

No ranking on missing or unverified numerical inputs, no arbitrary backtests,
no trading signals. Two scoreboards: market-only and evidence-backed equity.
"""
from __future__ import annotations
import csv
import hashlib
import html
import io
import json
import math
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean, stdev
from .analytics import wilder_rsi
from .constraints import instrument_constraints, OIL_EXPOSURE_VALUES
from .market_calendar import session_age, session
from .research_bundle import load_bundle, SYNTHETIC

WEIGHTS = {'momentum_20':.30,'momentum_60':.20,'volatility_20':.20,
           'drawdown_60':.15,'turnover_20':.15}
MAX_INSTRUMENTS = 5000


def _bounded(x, low, high):
    return min(1.,max(0.,(x-low)/(high-low)))


def _market_score(m):
    parts = {
        'momentum_20':_bounded(m['momentum_20'],-.25,.25),
        'momentum_60':_bounded(m['momentum_60'],-.40,.40),
        'volatility_20':1-_bounded(m['volatility_20'],.10,1.00),
        'drawdown_60':_bounded(m['max_drawdown_60'],-.50,0),
        'turnover_20':_bounded(math.log10(max(1,m['avg_daily_turnover_eur_20'])),4,8),
    }
    return round(sum(100*WEIGHTS[k]*v for k,v in parts.items()),2),parts


def _score_indicators(dated_prices):
    """Uses the last 61 *aligned* sessions; timestamps must be supplied.

    20/60 here means aligned trading observations, never calendar days.
    """
    if len(dated_prices)<61: return None
    last=dated_prices[-61:]
    closes=[float(z[1]) for z in last]
    turnover=[float(z[1]*z[2]) for z in last]
    if not all(math.isfinite(x) and x>0 for x in closes):
        raise ValueError('Invalid EUR close for screening')
    if not all(math.isfinite(x) and x>=0 for x in turnover):
        raise ValueError('Invalid EUR turnover for screening')
    rr=[closes[i]/closes[i-1]-1 for i in range(1,len(closes))]
    peak=closes[0];drawdown=0.
    for p in closes:
        peak=max(peak,p)
        drawdown=min(drawdown,p/peak-1)
    m={'momentum_20':round(closes[-1]/closes[-21]-1,7),
       'momentum_60':round(closes[-1]/closes[0]-1,7),
       'volatility_20':round(stdev(rr[-20:])*math.sqrt(252),7),
       'max_drawdown_60':round(drawdown,7),
       'avg_daily_turnover_eur_20':round(mean(turnover[-20:]),2),
       'rsi_wilder_14':round(wilder_rsi(closes),2),
       'aligned_observations':len(last),
       'first_observation':last[0][0], 'last_observation':last[-1][0]}
    return m


def _fx_dated_prices(bars, fx, currency):
    if currency=='EUR':
        return [(r['date'],Decimal(r['close']),Decimal(r['volume'])) for r in bars],None
    if currency!='USD':
        raise ValueError('Only EUR/USD supported; never compare local currencies directly')
    if not fx: return [],'MISSING_ECB_FX'
    lookup={x['date']:Decimal(x['usd_per_eur']) for x in fx}
    aligned=[(x['date'],Decimal(x['close'])/lookup[x['date']],Decimal(x['volume']))
             for x in bars if x['date'] in lookup]
    if not aligned or aligned[-1][0]!=bars[-1]['date']:
        return [],'LATEST_PRICE_HAS_NO_SAME_DAY_ECB_FX'
    return aligned,None


def _history_quality(dated_prices, venue):
    """Require a complete last 61 venue sessions and check for possible split jumps.

    A price series with 61 rows is not necessarily 61 *consecutive* sessions.
    Refuse a reliable-looking momentum score when bars are missing, even when
    the newest quote is fresh. Calendars beyond 2026 are fail-closed.
    """
    if len(dated_prices)<61:
        return {'verified':False,'reason':'INSUFFICIENT_61_ALIGNED_OBSERVATIONS',
                'missing_sessions':None,'largest_daily_move':None}
    last=dated_prices[-61:]
    try:
        start,end=date.fromisoformat(last[0][0]),date.fromisoformat(last[-1][0])
        expected=[]
        for offset in range((end-start).days+1):
            day=start+timedelta(days=offset)
            if session(day,venue):expected.append(day.isoformat())
    except ValueError:
        return {'verified':False,'reason':'HISTORY_SESSION_CALENDAR_UNAVAILABLE',
                'missing_sessions':None,'largest_daily_move':None}
    actual=[x[0] for x in last]
    if actual!=expected:
        missing=len(set(expected)-set(actual))
        return {'verified':False,'reason':'MISSING_OR_INVALID_TRADING_SESSIONS',
                'missing_sessions':missing,'largest_daily_move':None}
    prices=[x[1] for x in last]
    moves=[abs(prices[i]/prices[i-1]-1) for i in range(1,len(prices))]
    maximum=max(moves)
    # Conservative review threshold: catches 3:2, 4:3 and 5:4 unadjusted
    # split-like discontinuities. Legitimate large moves are also flagged;
    # this does NOT prove a split or validate sub-15% corporate actions.
    if maximum>=Decimal('.15'):
        return {'verified':False,'reason':'UNVERIFIED_CORPORATE_ACTION_OR_EXTREME_PRICE_JUMP',
                'missing_sessions':0,'largest_daily_move':round(float(maximum),6)}
    return {'verified':True,'reason':None,'missing_sessions':0,
            'largest_daily_move':round(float(maximum),6)}


def _point_in_time_source_status(manifest, asset, as_of, fx):
    if manifest['mode']==SYNTHETIC:
        return []
    metadata=[asset['prices']]
    if asset['currency']=='USD' and manifest.get('fx'):metadata.append(manifest['fx'])
    problems=[]
    for m in metadata:
        collected=m.get('retrieved_at_utc')
        if not collected:
            problems.append('MISSING_SOURCE_COLLECTION_DATE')
            continue
        try: retrieved=date.fromisoformat(collected[:10])
        except (TypeError,ValueError):
            problems.append('MALFORMED_SOURCE_COLLECTION_DATE')
            continue
        if retrieved>as_of:
            problems.append('SNAPSHOT_COLLECTED_AFTER_AS_OF')
    return sorted(set(problems))


def _format_metric(value):
    if value is None: return 'N/A'
    if isinstance(value,float): return f'{value:.4f}'
    return str(value)


def screen(bundle:Path, *, settings=None, max_age_sessions=1):
    manifest,items,fx,events=load_bundle(Path(bundle))
    if len(items)>MAX_INSTRUMENTS: raise ValueError('Universe exceeds configured safety limit')
    reference=date.fromisoformat(manifest['as_of'])
    settings=settings or {'exclude_primary_oil':True,'exclude_additional_gold':True,
                          'avoid_duplicate_eurostoxx50':True}
    results=[]
    for asset,bars,facts in items:
        uid=asset['id'];warnings=[]
        flags=instrument_constraints(asset,settings,new_purchase=True)
        blocks=[x.code for x in flags if x.level=='BLOCKED']
        warnings.extend(x.code for x in flags if x.level!='BLOCKED')
        m=None;price_score=None;components=None;equity_score=None
        latest=bars[-1]['date']
        try:
            stale=session_age(reference,date.fromisoformat(latest),asset['venue'])
        except ValueError as exc:
            stale=None;warnings.append('UNVERIFIED_MARKET_CALENDAR_OR_PRICE_SESSION:'+str(exc))
        if stale is not None and stale>max_age_sessions:
            warnings.append(f'STALE_BY_{stale}_MARKET_SESSIONS')
        data,fx_issue=_fx_dated_prices(bars,fx,asset['currency'])
        if fx_issue: warnings.append(fx_issue)
        history=_history_quality(data,asset['venue'])
        if history['reason']: warnings.append(history['reason'])
        pit_issues=_point_in_time_source_status(manifest,asset,reference,fx)
        warnings.extend(pit_issues)
        # yfinance provides Yahoo Close prices (auto_adjust=False); a documented split during the
        # last 61 observations invalidates raw price momentum until adjusted.
        split_dates=asset['prices'].get('split_dates',[])
        if any(isinstance(d,str) and d>=bars[max(0,len(bars)-61)]['date'] and d<=latest for d in split_dates):
            warnings.append('UNADJUSTED_SPLIT_REQUIRES_CORPORATE_ACTION_REVIEW')
        exposure = str(asset.get('oil_exposure') or '').strip().lower()
        if exposure not in OIL_EXPOSURE_VALUES or exposure in ('indirect', 'material'):
            # Indirect/material is NOT proof of a non-predominant position.
            warnings.append('UNVERIFIED_OIL_MATERIALITY')
        if manifest['mode']!=SYNTHETIC and not asset.get('sector'):
            warnings.append('UNVERIFIED_SECTOR_OR_OIL_EXPOSURE')
        market_ready=(not blocks and stale is not None and stale<=max_age_sessions
                      and not fx_issue and history['verified'] and not pit_issues
                      and 'UNVERIFIED_SECTOR_OR_OIL_EXPOSURE' not in warnings
                      and 'UNVERIFIED_OIL_MATERIALITY' not in warnings
                      and 'UNADJUSTED_SPLIT_REQUIRES_CORPORATE_ACTION_REVIEW' not in warnings)
        if market_ready:
            m=_score_indicators(data)
            price_score,components=_market_score(m)
        fundamentals_warning=[]
        if facts and asset.get('asset_type','EQUITY')=='EQUITY':
            revenue=Decimal(facts['revenue_usd']);income=Decimal(facts['net_income_usd'])
            margin=float(income/revenue)
            if not math.isfinite(margin): raise ValueError('Invalid fundamental ratio')
            if manifest['mode']!=SYNTHETIC:
                fundamental_meta=asset.get('fundamentals') or {}
                collected=fundamental_meta.get('retrieved_at_utc')
                if not collected:
                    fundamentals_warning.append('MISSING_FUNDAMENTAL_COLLECTION_DATE')
                else:
                    try:
                        if date.fromisoformat(collected[:10])>reference:
                            fundamentals_warning.append('FUNDAMENTALS_COLLECTED_AFTER_AS_OF')
                    except (TypeError,ValueError):
                        fundamentals_warning.append('MALFORMED_FUNDAMENTAL_COLLECTION_DATE')
                if fundamental_meta.get('provider')=='SEC_COMPANYFACTS' and not facts.get('source_filing_accession'):
                    fundamentals_warning.append('MISSING_SEC_FILING_ACCESSION')
            fundamental={'net_margin_annual':round(margin,6),
                'period_end':facts['period_end'],
                'last_filed':max(facts['revenue_filed_date'],facts['earnings_filed_date']),
                'fundamental_provider':asset['fundamentals']['provider'],
                'source_filing_accession':facts.get('source_filing_accession')}
            if price_score is not None and not fundamentals_warning:
                quality=_bounded(margin,-.2,.4)*100
                equity_score=round(.85*price_score+.15*quality,2)
        else:
            fundamental=None
            if asset.get('asset_type','EQUITY')=='EQUITY': warnings.append('MISSING_AS_OF_FUNDAMENTALS')
        warnings.extend(fundamentals_warning)
        if blocks: status='BLOCKED_BY_POLICY'
        elif not market_ready: status='INCOMPLETE_NO_RANK'
        elif manifest['mode']==SYNTHETIC: status='DEMO_RANK_NOT_REAL_MARKET'
        else: status='RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY'
        upcoming=[{'event_id':event['event_id'], 'asset_id':event['asset_id'],
                   'event_date':event['event_date'], 'published_date':event['published_date'],
                   'category':event['category'],'description':event['description'],
                   'source_url':event['source_url']}
                  for event in events if event['asset_id'] in (uid,'*')]
        results.append({'id':uid,'name':asset['name'],'isin':asset.get('isin',''),
            'asset_type':asset.get('asset_type','EQUITY'),
            'sector':asset.get('sector',''),'venue':asset['venue'],
            'currency':asset['currency'],'status':status,'blocking_constraints':blocks,
            'warnings':warnings,'price_source':asset['prices']['provider'],
            'price_sha256':asset['prices']['sha256'],
            'price_source_url':asset['prices'].get('source_url',''),
            'last_price_session':latest,'stale_sessions':stale,
            'market_score':price_score,'market_components':components,
            'equity_fundamental_score':equity_score,
            'market_metrics':m,'fundamental_metrics':fundamental,
            'history_quality':history,
            'documented_events_not_causal_predictions':upcoming,
            'trade_ready':False,
            'research_rationale':'Scores compare historical indicators, NOT expected future returns.'})
    # Rank only homogeneous score types. Missing data never receives zero score.
    ordered=sorted((r for r in results if r['market_score'] is not None),
                   key=lambda r:(-r['market_score'],r['id']))
    for i,r in enumerate(ordered,1):r['market_rank']=i
    equity=sorted((r for r in results if r['equity_fundamental_score'] is not None),
                  key=lambda r:(-r['equity_fundamental_score'],r['id']))
    for i,r in enumerate(equity,1):r['equity_fundamental_rank']=i
    results=sorted(results,key=lambda r:(r.get('market_rank',10**9),r['id']))
    return {'schema_version':1,'as_of':manifest['as_of'],'dataset_mode':manifest['mode'],
        'dataset_manifest_sha256':hashlib.sha256((Path(bundle)/'manifest.json').read_bytes()).hexdigest(),
        'universe_size':len(items),'documented_event_count':len(events),
        'documented_events':events,'ranked_count':len(ordered),
        'fundamentals_ranked_count':len(equity),'weights':WEIGHTS,
        'method':'Fixed bounded transparent 20/60 aligned-session momentum + volatility/drawdown + EUR turnover. Optional net-margin-only equity overlay, NOT a fundamental valuation.',
        'results':results,'limitations':[
            'Not a forecast or trade recommendation; no real bid/ask, corporate actions, intraday or broker verification.',
            'Closing dates for US/EU markets may not represent synchronous information sets.',
            'Continuity gate requires every last 61 trading sessions (2026 calendars only).',
            'Source bytes collected after as_of do not qualify as point-in-time evidence.',
            'Daily absolute close-to-close moves >=15% block ranking pending corporate-action/price review; heuristic can flag real moves and cannot detect all smaller actions.',
            'ECB same-calendar-date fixings precede US equity close by hours: USD/EUR conversion is an asynchronous reference convention, not an executable synchronous P/L or hedge.',
            'Yahoo/yfinance Close (auto_adjust=False) excludes dividends from returns; split adjustments depend on the provider and require review; research use subject to provider license.',
            'Annual SEC net margin is not a substitute for sector-specific valuations, debt, guidance or catalysts.',
            'Ranking only considers EUR-converted same-date aligned observations and available evidence.',
            'No sector-relative valuation ranking or predictive calibration is claimed.']}


def write_screening(report:dict,output:Path):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'BLOCK_B_SCREENING.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    fields=['market_rank','equity_fundamental_rank','id','name','sector','currency','status',
            'market_score','equity_fundamental_score','last_price_session','stale_sessions',
            'momentum_20','momentum_60','volatility_20','max_drawdown_60',
            'avg_daily_turnover_eur_20','net_margin_annual','warnings']
    handle=io.StringIO(newline='');w=csv.DictWriter(handle,fieldnames=fields,lineterminator='\n');w.writeheader()
    for row in report['results']:
        metrics=row['market_metrics'] or {};fund=row['fundamental_metrics'] or {}
        w.writerow({k:(row.get(k) if k in row else metrics.get(k,fund.get(k,'')))
                    if k!='warnings' else ';'.join(row['warnings']) for k in fields})
    (output/'BLOCK_B_SCREENING.csv').write_text(handle.getvalue(),encoding='utf-8')
    lines=['# Blocco B — screening trasparente','',
           f"- **As-of:** {report['as_of']}",
           f"- **Dataset:** {report['dataset_mode']}",
           f"- **Universo:** {report['universe_size']} · ordinabili: {report['ranked_count']} · con overlay fondamentale: {report['fundamentals_ranked_count']} · eventi documentati: {report['documented_event_count']}",
           f"- **Manifest SHA-256:** `{report['dataset_manifest_sha256']}`",'',
           '> **RICERCA, NON SEGNALI DI TRADING.** Se il dataset è sintetico, ogni ranking è esclusivamente dimostrativo.', '',
           '## Ordinamento su indicatori di mercato (non previsioni)','',
           '| Rank | Strumento | Score storico | Score con fondamentali | Stato | Avvertenze |',
           '|---:|---|---:|---:|---|---|']
    for r in report['results']:
        clean=lambda z:str(z).replace('|','\\|').replace('\n',' ')
        lines.append(f"| {r.get('market_rank','—')} | {clean(r['name'])} | {r['market_score'] if r['market_score'] is not None else '—'} | {r['equity_fundamental_score'] if r['equity_fundamental_score'] is not None else '—'} | {r['status']} | {clean(', '.join(r['warnings']))} |")
    lines+=['','## Calendario di eventi (non previsione causale)']
    for ev in report['documented_events']:
        lines.append(f"- {ev['asset_id']} · {ev['event_date']} ({ev['category']}; pubblicato {ev['published_date']}): {ev['description'].replace('|',' ')}")
    lines+=['','## Metodologia',report['method'],'', '## Limiti']+['- '+s for s in report['limitations']]
    (output/'BLOCK_B_SCREENING.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    rows=''.join('<tr>'+''.join(f'<td>{html.escape(str(cell))}</td>' for cell in [
        r.get('market_rank','—'),r['name'],r['market_score'] if r['market_score'] is not None else '—',
        r['equity_fundamental_score'] if r['equity_fundamental_score'] is not None else '—',
        r['status'],', '.join(r['warnings'])])+'</tr>' for r in report['results'])
    title='Blocco B — Screening dimostrativo' if report['dataset_mode']==SYNTHETIC else 'Blocco B — Screening dati esterni non verificati'
    html_text=f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{font-family:system-ui;max-width:1200px;margin:auto;padding:25px;color:#172337}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #ccc;text-align:left;vertical-align:top}}th{{background:#edf2f8}}.alert{{border-left:5px solid #a66d0f;background:#fff4d9;padding:15px}}.scroll{{overflow-x:auto}}</style></head><body><h1>{html.escape(title)}</h1><p>Data di riferimento {html.escape(report['as_of'])} — {report['universe_size']} strumenti; {report['ranked_count']} ordinabili.</p><p class="alert">Non è una previsione né una raccomandazione di acquisto. Prezzi eseguibili e dati fondamentali specifici non sono certificati. Nessun ordine automatico.</p><div class="scroll"><table><thead><tr><th>Rank storico</th><th>Strumento</th><th>Score</th><th>Overlay fondamentale</th><th>Stato</th><th>Limiti</th></tr></thead><tbody>{rows}</tbody></table></div><h2>Limitazioni</h2><ul>{''.join('<li>'+html.escape(s)+'</li>' for s in report['limitations'])}</ul><p>Per verificare i calcoli, consultare BLOCK_B_SCREENING.json e il manifest SHA-256.</p></body></html>'''
    (output/'block_b_dashboard.html').write_text(html_text,encoding='utf-8')
    return output
