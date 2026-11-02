"""Block A integrated CLI. All financial prices are snapshots, NOT executable."""
from __future__ import annotations
import argparse, csv, json, sys
from datetime import date
from pathlib import Path
from .core import Fees, evaluate_position, apply_loss_carryforward, validate_allocation, D
from .analytics import indicators, returns, pearson_aligned
from .quality import read_strict_csv, validate_instrument_mapping, audit, readiness, to_json
from .constraints import instrument_constraints, portfolio_constraints
from .decision import save_decision
from .tax_engine import FiscalRegistry, DIFFERENT

ROOT = Path(__file__).resolve().parents[2]


def records(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _source_rows():
    instruments = read_strict_csv(ROOT/'data/snapshots/instruments.csv')
    quotes = read_strict_csv(ROOT/'data/snapshots/verified_quotes.csv')
    validate_instrument_mapping(instruments)
    return instruments, quotes


def _history_metrics(outdir, as_of):
    history_file = outdir/'provider_history_unverified.csv'
    if not history_file.exists():
        return
    by_id = {}
    for item in records(history_file):
        by_id.setdefault(item['id'], []).append((item['date'], float(item['close_adjusted'])))
    price_map = {}
    metrics = []
    for uid, values in by_id.items():
        values.sort()
        dates = [day for day, _ in values]
        if len(dates) != len(set(dates)):
            raise ValueError(f'Duplicate historical dates for {uid}')
        if dates[-1] > as_of:
            raise ValueError(f'Future historical data for {uid}')
        price_map[uid] = dict(values)
        metrics.append({'id':uid, **indicators([v for _,v in values]),
                        'last_date':dates[-1], 'source_status':'UNVERIFIED_HISTORY'})
    write_csv(outdir/'technical_indicators_UNVERIFIED.csv', metrics)
    correlations = []
    for ix, a in enumerate(sorted(price_map)):
        for b in sorted(price_map)[ix+1:]:
            days = sorted(set(price_map[a]) & set(price_map[b]))
            if len(days) < 21:
                continue
            # Align dates before returns; currency-level comparability is NOT guaranteed.
            corr = pearson_aligned(returns([price_map[a][d] for d in days]),
                                   returns([price_map[b][d] for d in days]))
            correlations.append({'id_a':a,'id_b':b,'observations':len(days)-1,
                'correlation_local_currency_UNVERIFIED':corr,
                'status':'REVIEW_CURRENCY_AND_NON_SYNC_MARKET_CLOSES'})
    write_csv(outdir/'correlations_UNVERIFIED.csv', correlations)


def make_report(outdir: Path, case_path=None):
    outdir.mkdir(parents=True, exist_ok=True)
    settings = json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
    config = json.loads((ROOT/'config/portfolios.json').read_text(encoding='utf-8'))
    instruments, quotes = _source_rows()
    known = {x['id']: x for x in instruments}
    lookup = {x['id']: x for x in quotes}
    case_file = Path(case_path) if case_path is not None else ROOT/'data/fixtures/investment_case_example.json'
    case = json.loads(case_file.read_text(encoding='utf-8'))
    if case_path is None and case['as_of'] != settings['as_of']:
        raise ValueError('Demo as-of differs from configured as-of')
    as_of = date.fromisoformat(case['as_of'])
    statuses = audit(instruments, quotes, as_of, settings=settings)
    registry = FiscalRegistry.load(ROOT/'config/fiscal/rules_2026.json')
    (outdir/'quality_gates.json').write_text(json.dumps({'as_of':settings['as_of'],
        'statuses':to_json(statuses)}, indent=2, ensure_ascii=False), encoding='utf-8')
    fee = Fees(D(settings['broker_commission_rate']), D(settings['broker_commission_min_eur']),
        D(settings['broker_commission_max_eur']), D(settings['italian_equity_ftt_regulated_market_rate']))
    coverage = []
    for row in instruments:
        q = lookup.get(row['id'], {})
        stage = readiness(statuses, row['id'])
        coverage.append({'id':row['id'], 'name':row['name'], 'isin':row['isin'],
            'sector':row['sector'], 'profile':row['profile'], 'quote':q.get('price',''),
            'quote_currency':q.get('currency',''), 'quote_date':q.get('market_date',''),
            'quote_status':'HISTORICAL_SNAPSHOT' if q else 'MISSING',
            'source':q.get('source_url',''), 'fiscal_status':row['fiscal_status'],
            'research_readiness':stage['research_readiness'],
            'shortlist_readiness':stage['shortlist_readiness'],
            'pretrade_readiness':stage['pretrade_readiness'],
            'executable_now':'NO', 'notes':row['notes']})
    write_csv(outdir/'screening.csv', coverage)
    _history_metrics(outdir, settings['as_of'])
    results = []
    for p in config['portfolios']:
        validate_allocation(p['positions'],p['cash_eur'],settings['capital_eur'],settings['max_positions'])
        pflags = portfolio_constraints(p['positions'],p['cash_eur'],settings)
        for uid in p['positions']:
            if uid not in known:
                raise ValueError(f'Unknown portfolio instrument: {uid}')
            pflags += instrument_constraints(known[uid], settings)
        if any(readiness(statuses, uid)['shortlist_readiness'] == 'BLOCKED' for uid in p['positions']):
            raise ValueError(f'Quality hard BLOCK in {p["id"]}; report must fail closed')
        if any(flag.level == 'BLOCKED' for flag in pflags):
            raise ValueError(f'Hard exclusions violated by {p["id"]}: {[x.code for x in pflags]}')
        partial = any(readiness(statuses, uid)['shortlist_readiness'] != 'VERIFIED'
                      for uid in p['positions'])
        for scname, assumptions in config['scenarios'].items():
            gross=trading=ftt=fxcost=total=eligible_net=pending_net=D(0)
            for uid, capital in p['positions'].items():
                if uid not in assumptions:
                    raise ValueError(f'Missing hypothetical return for {uid}/{scname}')
                r = evaluate_position(capital, assumptions[uid], fee,
                    known[uid]['italian_ftt']=='yes',
                    settings['fx_transaction_cost_bps'] if known[uid]['trade_currency']=='USD' else 0)
                gross += r.gross_pnl_eur
                trading += r.buy_cost_eur+r.sell_cost_eur
                ftt += r.ftt_eur
                fxcost += r.fx_conversion_cost_eur
                total += r.net_pnl_before_unverified_costs_eur
                fiscal_rule = registry.get(known[uid]['asset_type'], as_of, known[uid].get('isin',''))
                event = 'gain' if r.net_pnl_before_unverified_costs_eur > 0 else 'loss'
                if fiscal_rule.category(event) == DIFFERENT and fiscal_rule.verification == 'DOCUMENTED_GENERIC':
                    eligible_net += r.net_pnl_before_unverified_costs_eur * fiscal_rule.taxable_factor
                else:
                    pending_net += r.net_pnl_before_unverified_costs_eur
            provisional = apply_loss_carryforward(max(D(0), eligible_net), settings['loss_carryforward_eur'])
            results.append({'portfolio':p['id'], 'scenario':scname,
                'invested_eur':sum(p['positions'].values()), 'cash_eur':p['cash_eur'],
                'gross_pnl_eur':str(gross), 'broker_commissions_eur':str(trading),
                'italian_ftt_assumption_eur':str(ftt), 'fx_conversion_cost_est_eur':str(fxcost),
                'net_pnl_excluding_market_spread_eur':str(total),
                'net_portfolio_return_pct':str((100*total/D(settings['capital_eur'])).quantize(D('.01'))),
                'equity_eligible_net_eur':str(eligible_net), 'etn_etc_pending_net_eur':str(pending_net),
                'provisional_equity_tax_offset_eur':str(provisional['potential_offset_eur']),
                'tax_status':'UNVERIFIED_PERSONAL_WALLET_FISCAL_RULE_REGISTRY',
                'scenario_status':'HYPOTHETICAL_INCOMPLETE' if partial else 'HYPOTHETICAL_NOT_PREDICTION',
                'assumptions_source':'config/portfolios.json - MANUALLY ASSIGNED NOT FORECAST',
                'market_bid_ask_spread_included':'NO',
                'constraint_warnings':';'.join(f.code for f in pflags if f.level=='REVIEW')})
    write_csv(outdir/'portfolio_scenarios.csv', results)
    lines=['# Investment research engine — as-of '+case['as_of'],'',
        '> **NOT LIVE QUOTES, NOT BUY SIGNALS.** Last reference close: '+settings['market_data_last_session'],
        '> Scenarios are synthetic assumptions. Some instruments lack quotes and/or fiscal confirmation.', '',
        f'Quote reference coverage: **{len(quotes)} / {len(instruments)}**.', '',
        '## Hypothetical portfolio scenarios (EUR)',
        '| Portfolio | Case | Gross P/L | Commissions | FTT assumption | FX estimate | Net P/L* | Status |',
        '|---|---|---:|---:|---:|---:|---:|---|']
    for row in results:
        lines.append(f"| {row['portfolio']} | {row['scenario']} | {row['gross_pnl_eur']} | {row['broker_commissions_eur']} | {row['italian_ftt_assumption_eur']} | {row['fx_conversion_cost_est_eur']} | {row['net_pnl_excluding_market_spread_eur']} | {row['scenario_status']} |")
    lines += ['', '*Costs are estimates; real spreads, custody charges and instrument-specific tax details unresolved.',
              'See DECISION_COMPARISON.md for a separate, reproducible comparison using DEMONSTRATION positions.',
              'Trade date, settlement date, and fiscal recognition date are not interchangeable.',
              'No scenario or research output is authorization to trade.', '']
    (outdir/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    save_decision(outdir, case, ROOT/'config/fiscal/rules_2026.json', settings=settings)
    return outdir


def refresh_yfinance(outdir: Path, min_coverage=0.80):
    """Optional free NON-VERIFIED history; aborts if coverage insufficient."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError('pip install -e .[data] required') from exc
    outdir.mkdir(parents=True, exist_ok=True)
    instruments, _ = _source_rows()
    downloaded, succeeded = [], set()
    for row in instruments:
        try:
            frame = yf.download(row['ticker'], period='1y', auto_adjust=True,
                                progress=False, threads=False)
            if frame.empty:
                raise ValueError('Empty history')
            values = frame['Close']
            if hasattr(values,'iloc') and len(values.shape)>1:
                values = values.iloc[:,0]
            from .analytics import _validated
            validated = _validated([float(v) for v in values])
            for (dt, _), v in zip(values.items(), validated):
                downloaded.append({'id':row['id'], 'date':str(dt.date()),
                    'close_adjusted':v,'provider':'yfinance',
                    'quality':'UNVALIDATED_PROVIDER_HISTORY'})
            succeeded.add(row['id'])
        except Exception as exc:
            print('FAILED',row['id'],type(exc).__name__,str(exc)[:150],file=sys.stderr)
    if len(succeeded)/len(instruments) < min_coverage:
        raise RuntimeError(f'Historical coverage {len(succeeded)}/{len(instruments)} below threshold {min_coverage:.0%}')
    write_csv(outdir/'provider_history_unverified.csv', downloaded)
    print(f'UNVERIFIED historical download {len(succeeded)}/{len(instruments)} instruments')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Research only: no orders, no broker API')
    ap.add_argument('command', choices=['report','refresh'])
    ap.add_argument('--output',default=str(ROOT/'reports/generated'))
    ap.add_argument('--case',type=Path,default=None,help='Local case JSON; never automatically uploaded')
    args = ap.parse_args(argv)
    out=Path(args.output)
    if args.command == 'refresh':
        refresh_yfinance(out)
    else:
        make_report(out, case_path=args.case)
        print('Wrote', out/'REPORT.md')

if __name__ == '__main__':
    main()
