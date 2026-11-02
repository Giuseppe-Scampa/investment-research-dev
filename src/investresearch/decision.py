"""Evidence-labelled comparison of inaction, current holdings and a new trade.

All prices are illustrative references, not executable. Fiscal recognition and
future re-entry are not certified or automatically modeled.
"""
from __future__ import annotations
import hashlib, json
from datetime import date
from pathlib import Path
from .core import Fees, D, cents
from .cost_engine import trade_costs, affordable_units, break_even_sell_unit_price
from .positions import sale_cost_basis
from .tax_engine import FiscalRegistry, classify_realization, expired_potential
from .tax_netting import net_realizations
from .quality import valid_isin
from .market_calendar import session_age
from .constraints import instrument_constraints

DEMO = 'SYNTHETIC_DEMONSTRATION_NOT_PERSONAL_HOLDINGS'
USER = 'USER_SUPPLIED_UNVERIFIED'


def _stable_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _outcome_position(p, case, registry, fees):
    if p['account_id'] != case['account_id']:
        raise ValueError('Cross-account position; no implicit wallet matching')
    date_as_of = date.fromisoformat(case['as_of'])
    if not valid_isin(p.get('isin','')):
        raise ValueError('Existing position missing valid ISIN')
    quote_date = date.fromisoformat(p['quote_date'])
    if quote_date.year != 2026:
        raise ValueError(f"Stale quotation outside supported year for {p['position_id']}")
    if quote_date > date_as_of:
        raise ValueError(f"Future quotation for {p['position_id']}")
    venue = p['venue']
    age = session_age(date_as_of, quote_date, venue)
    if age > int(case.get('max_quote_age_sessions', 1)):
        raise ValueError(f"Stale quotation for {p['position_id']}: {age} sessions")
    # Explicit future date can be modeled only as an illustrative transaction;
    # the default as-of is NOT an assertion about a tax-recognition date.
    realization_date = date.fromisoformat(p.get('realization_date', case['as_of']))
    if realization_date.year != date_as_of.year or realization_date < quote_date:
        raise ValueError('Realization date inconsistent with quote/fiscal year')
    rule = registry.get(p['asset_type'], realization_date, p['isin'])
    qty = D(p['sale_quantity'])
    if case['fixture_kind'] == USER and p.get('tax_cost_method') != 'BROKER_REPORTED_AVERAGE':
        raise ValueError('Real holdings require explicit broker-reported fiscal average; illustrative lots not certified')
    tax_basis, method = sale_cost_basis(p, qty)
    sale = trade_costs(qty, p['reference_unit_price_eur'], fees, side='sell',
                       italy_ftt_status=p.get('ftt_scope','unknown'),
                       fx_bps=p.get('fx_bps'), spread_bps=p.get('spread_bps'))
    taxes = classify_realization(sale['net_proceeds_eur'], tax_basis, rule)
    eligible_gain = D(taxes['compensable_eur']) if taxes['category'] == 'REDDITI_DIVERSI' and taxes['event'] == 'gain' else D(0)
    eligible_loss = D(taxes['compensable_eur']) if taxes['category'] == 'REDDITI_DIVERSI' and taxes['event'] == 'loss' else D(0)
    return {'position_id':p['position_id'], 'isin':p['isin'], 'name':p['name'],
            'realization_date':realization_date.isoformat(), 'quote_date':quote_date.isoformat(),
            'quote_age_sessions':age, 'sale_quantity':str(qty),
            'reference_price_eur':p['reference_unit_price_eur'],
            'sale_cash_proceeds_eur':sale['net_proceeds_eur'], 'tax_basis_eur':str(tax_basis),
            'cost_method':method, 'hypothetical_realized_net_eur':taxes['net_eur'],
            'compensable_gain_eur':str(cents(eligible_gain)),
            'compensable_loss_eur':str(cents(eligible_loss)),
            'compensable_eur':taxes['compensable_eur'], 'fiscal_event':taxes['event'],
            'category':taxes['category'], 'tax_rate':taxes['tax_rate'],
            'fiscal_rule':rule.rule_id, 'tax_verification':taxes['fiscal_status'],
            'valuation_status':'INCOMPLETE_NO_EXECUTABLE_BID_ASK', 'costs':sale}


def _case_new_trade(n, case, registry, fees, wallet, settings):
    date_as_of = date.fromisoformat(case['as_of'])
    if not valid_isin(n.get('isin','')):
        raise ValueError('New instrument missing valid ISIN')
    flags = instrument_constraints({'name':n.get('name',''), 'sector':n.get('sector',''),
        'oil_exposure':n.get('oil_exposure',''), 'index_memberships':n.get('index_memberships',[]),
        'index_membership_status':n.get('index_membership_status','UNKNOWN')}, settings or {}, new_purchase=True)
    if any(flag.level == 'BLOCKED' for flag in flags):
        raise ValueError('Excluded new instrument: '+str([f.code for f in flags]))
    rule = registry.get(n['asset_type'], date_as_of, n['isin'])
    buy = trade_costs(n['quantity'], n['purchase_unit_price_eur'], fees, side='buy',
                      italy_ftt_status=n.get('ftt_scope','unknown'),
                      fx_bps=n.get('fx_bps'), spread_bps=n.get('spread_bps'))
    sell = trade_costs(n['quantity'], n['hypothetical_sale_unit_price_eur'], fees, side='sell',
                       italy_ftt_status=n.get('ftt_scope','unknown'),
                       fx_bps=n.get('fx_bps'), spread_bps=n.get('spread_bps'))
    affordable = affordable_units(case['investment_budget_eur'], n['purchase_unit_price_eur'], fees,
                                  italy_ftt_status=n.get('ftt_scope','unknown'),
                                  fx_bps=n.get('fx_bps'), spread_bps=n.get('spread_bps'))
    if D(buy['outlay_eur']) > D(case['investment_budget_eur']):
        raise ValueError('New investment purchase plus fees exceeds cash budget')
    realized = classify_realization(sell['net_proceeds_eur'], buy['outlay_eur'], rule)
    event = {'realization_date':case['as_of'], 'category':realized['category'],
             'fiscal_event':realized['event'], 'compensable_eur':realized['compensable_eur'],
             'tax_rate':realized['tax_rate'], 'hypothetical_realized_net_eur':realized['net_eur'],
             'position_id':'NEW_INVESTMENT'}
    tax = net_realizations([event], wallet, case['account_id'], date_as_of.year, case['tax_regime'])
    gross_pnl = D(realized['net_eur'])
    tax_due = D(tax['estimated_income_tax_eur'])
    eligible = D(tax['eligible_net_gain_eur'])
    return {'name':'C_NEW_INVESTMENT', 'status':'HYPOTHETICAL_NOT_PREDICTION',
            'isin':n['isin'], 'quantity':n['quantity'], 'buy':buy, 'sell':sell,
            'cash_budget_eur':case['investment_budget_eur'],
            'cash_after_buy_eur':str(cents(D(case['investment_budget_eur']) - D(buy['outlay_eur']))),
            'affordable_units_including_commissions':affordable,
            'economic_profit_before_unknown_costs_eur':realized['net_eur'],
            'economic_profit_after_estimated_tax_eur':str(cents(gross_pnl - tax_due)),
            'estimated_income_tax_eur':tax['estimated_income_tax_eur'],
            'estimated_transaction_costs_eur':str(cents(D(buy['total_explicit_cost_eur']) + D(sell['total_explicit_cost_eur']))),
            'eligible_gain_eur':str(cents(eligible)),
            'fiscal_category':realized['category'], 'wallet':tax['wallet'],
            'fiscal_status':tax['fiscal_status'],
            'break_even_unit_sale_price_eur':str(break_even_sell_unit_price(
                n['quantity'], n['purchase_unit_price_eur'], fees,
                italy_ftt_status=n.get('ftt_scope','unknown'), fx_bps=n.get('fx_bps'),
                spread_bps=n.get('spread_bps'))),
            'constraint_warnings':[x.code for x in flags if x.level != 'BLOCKED'],
            'warning':'Synthetic return only; no bid/ask, forecast, broker recognized tax event or verified trade date'}


def evaluate_case(case, registry: FiscalRegistry, fees=None, settings=None):
    fees = fees or Fees()
    if case.get('fixture_kind') not in (DEMO,USER):
        raise ValueError('Unknown input kind')
    date_as_of = date.fromisoformat(case['as_of'])
    if date_as_of.year != 2026:
        raise ValueError('The decision comparison is 2026-only until rules are versioned')
    wallet = case['tax_wallets']
    relevant_expiry = [w for w in expired_potential(wallet, date_as_of.year)
                       if w['account_id'] == case['account_id']]
    existing = [_outcome_position(p, case, registry, fees) for p in case['existing_positions']]
    net = net_realizations(existing, wallet, case['account_id'], date_as_of.year, case['tax_regime'])
    transaction_costs = sum((D(p['costs']['total_explicit_cost_eur']) for p in existing), D(0))
    tax_avoided = D(net['wallet']['potential_tax_avoided_eur'])
    tax_due = D(net['estimated_income_tax_eur'])
    # This compares incremental cash friction & taxes against retaining the
    # unrealised holdings. It is NOT an overall gain/loss or rebuy forecast.
    incremental_effect = cents(tax_avoided - tax_due - transaction_costs)
    alternative_b = {'name':'B_REALIZE_EXISTING',
                     'status':'ESTIMATED_NEEDS_REAL_PRICES_AND_BROKER_TAX_BASIS',
                     'positions':existing, 'eligible_net_gain_eur':net['eligible_net_gain_eur'],
                     'gross_eligible_gains_eur':net['different_gross_gains_eur'],
                     'gross_eligible_losses_eur':net['different_gross_losses_eur'],
                     'same_year_losses_applied_eur':net['same_year_losses_applied_eur'],
                     'unused_current_year_loss_eur':net['unused_current_year_loss_eur'],
                     'wallet':net['wallet'], 'fiscal_timeline':net['timeline'],
                     'fiscal_status':net['fiscal_status'],
                     'unresolved_tax_positions':net['unresolved_tax_positions'],
                     'total_sale_execution_costs_eur':str(cents(transaction_costs)),
                     'estimated_income_tax_eur':net['estimated_income_tax_eur'],
                     'estimated_capital_income_tax_eur':net['estimated_capital_income_tax_eur'],
                     'estimated_incremental_tax_and_execution_effect_eur':str(incremental_effect),
                     'incremental_effect_note':'Tax offset - tax triggered - sale execution friction; excludes rebuy, market movement and uncertain tax basis; NOT realised performance',
                     'reentry_assessment':'NOT_MODELLED; rebuy costs/legal/tax effects require independent assessment'}
    hypothetical = _case_new_trade(case['new_investment'], case, registry, fees, wallet, settings)
    return {'as_of':case['as_of'], 'mode':case['fixture_kind'], 'account_id':case['account_id'],
            'A_DO_NOTHING':{'name':'A_DO_NOTHING', 'status':'BASELINE_NO_TRADES',
                'potential_expiring_balance':relevant_expiry,
                'note':'Expiry is conditional on verified wallet balance and absent intervening offsets'},
            'B_REALIZE_EXISTING':alternative_b, 'C_NEW_INVESTMENT':hypothetical,
            'research_status':'INCOMPLETE_NEVER_TRADE_READY'}


def _load_events(path: Path):
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _write_events(path: Path, events):
    path.write_text(''.join(json.dumps(event,ensure_ascii=False,sort_keys=True)+'\n' for event in events), encoding='utf-8')


def record_human_decision(outdir: Path, decision_id: str, human_decision: str, observed_outcome=None):
    """Explicit human annotation in a durable append-only history (never invented)."""
    if not human_decision or not isinstance(human_decision,str):
        raise ValueError('Decision must be an explicit, nonempty human statement')
    path = Path(outdir)/'decision_ledger.jsonl'
    events = _load_events(path)
    if not any(e.get('id')==decision_id for e in events):
        raise ValueError('Unknown decision ID')
    event = {'id':decision_id, 'type':'HUMAN_ANNOTATION',
             'human_decision':human_decision, 'observed_outcome':observed_outcome}
    if not events or events[-1] != event:
        events.append(event)
        _write_events(path, events)
    snapshot = Path(outdir)/'decision_ledger.json'
    if snapshot.exists():
        data = json.loads(snapshot.read_text(encoding='utf-8'))
        if data.get('id') == decision_id:
            data.update(human_decision=human_decision, observed_outcome=observed_outcome)
            snapshot.write_text(json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    return event


def save_decision(outdir: Path, case: dict, rulefile: Path, settings=None):
    outdir.mkdir(parents=True,exist_ok=True)
    registry = FiscalRegistry.load(rulefile)
    result = evaluate_case(case, registry, settings=settings)
    input_hash = hashlib.sha256(_stable_bytes({'case':case,
        'rule_registry':json.loads(Path(rulefile).read_text(encoding='utf-8'))})).hexdigest()
    decision_id = 'research-' + input_hash[:16]
    result['decision_id'] = decision_id
    result['input_sha256'] = input_hash
    result['thesis'] = 'Compare inaction / existing realized gain / hypothetical new position'
    result['risks'] = ['No executable order book', 'Actual tax wallet unconfirmed',
        'Broker fiscal recognition date unconfirmed', 'Unknown spread/product costs',
        'Tax/legal and market effects of rebuy not modeled']
    ledger_path = outdir/'decision_ledger.jsonl'
    ledger_snapshot = outdir/'decision_ledger.json'
    events = _load_events(ledger_path)
    existing_snapshot = json.loads(ledger_snapshot.read_text(encoding='utf-8')) if ledger_snapshot.exists() else None
    first_event = {'id':decision_id, 'type':'RESEARCH_CREATED', 'as_of':case['as_of'],
        'software_version':'v3-block-a', 'input_sha256':input_hash,
        'thesis':result['thesis'],
        'evidence':['2026 rules and user input marked unverified' if case['fixture_kind']==USER
                    else '2026 rules and explicitly synthetic fixture'],
        'alternatives':['A_DO_NOTHING','B_REALIZE_EXISTING','C_NEW_INVESTMENT'],
        'risks':result['risks']}
    if not any(e.get('id')==decision_id and e.get('type')=='RESEARCH_CREATED' for e in events):
        events.append(first_event)
    # Preserve explicit edits to the previous snapshot, including old decisions
    # when a new scenario replaces the latest report.
    if existing_snapshot and existing_snapshot.get('human_decision') is not None:
        old_id = existing_snapshot.get('id')
        annotation={'id':old_id,'type':'HUMAN_ANNOTATION',
                    'human_decision':existing_snapshot['human_decision'],
                    'observed_outcome':existing_snapshot.get('observed_outcome')}
        if not any(e == annotation for e in events):
            events.append(annotation)
    _write_events(ledger_path, events)
    annotations = [e for e in events if e.get('id')==decision_id and e.get('type')=='HUMAN_ANNOTATION']
    latest = annotations[-1] if annotations else {}
    result['human_decision'] = latest.get('human_decision')
    result['observed_outcome'] = latest.get('observed_outcome')
    snapshot = {**first_event,'human_decision':result['human_decision'],
                'observed_outcome':result['observed_outcome']}
    ledger_snapshot.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    (outdir/'decision_comparison.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    a,b,c = result['A_DO_NOTHING'],result['B_REALIZE_EXISTING'],result['C_NEW_INVESTMENT']
    note = ('**Input:** fixture interamente sintetica, non posizioni personali.' if case['fixture_kind']==DEMO
            else '**Input:** portafoglio fornito dall’utente e non verificato indipendentemente.')
    lines = ['# Confronto decisionale — Block A V3', '',
        f"**Data as-of:** {case['as_of']} | **Input SHA-256:** `{input_hash}`", '',
        f'> {note} Prezzi indicativi non eseguibili; nessun ordine, nessuna previsione.', '',
        '| Alternativa | Guadagno diverso dopo perdite correnti | Offset zainetto | Imposta evitata* | Imposta stimata* | Effetto incrementale* |',
        '|---|---:|---:|---:|---:|---:|',
        f"| A — Non intervenire | €0 | €0 | €0 | €0 | €0 |",
        f"| B — Realizzare posizioni esistenti | €{b['eligible_net_gain_eur']} | €{b['wallet']['compensated_eur']} | €{b['wallet']['potential_tax_avoided_eur']} | €{b['estimated_income_tax_eur']} | €{b['estimated_incremental_tax_and_execution_effect_eur']} |",
        f"| C — Nuovo investimento ipotetico | €{c['eligible_gain_eur']} | €{c['wallet']['compensated_eur']} | €{c['wallet']['potential_tax_avoided_eur']} | €{c['estimated_income_tax_eur']} | n/a |", '',
        f"**B — Perdite dello stesso anno applicate:** €{b['same_year_losses_applied_eur']}; **costi di vendita espliciti:** €{b['total_sale_execution_costs_eur']}.",
        f"**C — Profitto ipotetico netto di commissioni e imposta stimata:** €{c['economic_profit_after_estimated_tax_eur']}",
        f"**C — Cassa residua dopo acquisto:** €{c['cash_after_buy_eur']}; **pareggio unitario indicativo:** €{c['break_even_unit_sale_price_eur']}", '',
        '* Solo simulazioni condizionate: stime fiscali, FX e spread non certificati; l’effetto incrementale B è risparmio fiscale meno imposte innescate e frizioni di uscita, NON performance della posizione, e NON include eventuale riacquisto.',
        'I guadagni diversi sono compensati con perdite precedenti o dello stesso giorno, **non con perdite successive**; il saldo del deposito e le date fiscali sono da verificare.',
        'FTT, classificazioni dei titoli complessi e oneri fiscalmente deducibili non sono certificati.',
        'Non eseguire operazioni sulla base di questi numeri.', '']
    (outdir/'DECISION_COMPARISON.md').write_text('\n'.join(lines),encoding='utf-8')
    return result
