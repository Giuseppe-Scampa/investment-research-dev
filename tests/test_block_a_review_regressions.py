"""Independent checks prompted by two external PR reviews (Nov 2026).

These tests cover regression paths not exercised by the original V3 suite.
They are illustrative checks, NOT a broker's certified tax computation.
"""
from __future__ import annotations
import copy, json
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from investresearch.core import Fees
from investresearch.cost_engine import break_even_sell_unit_price, trade_costs
from investresearch.cli import ROOT, make_report
from investresearch.constraints import instrument_constraints
from investresearch.decision import evaluate_case, save_decision, record_human_decision, USER
from investresearch.tax_engine import FiscalRegistry
from investresearch.tax_netting import net_realizations
from investresearch.quality import audit
from investresearch.dashboard import html_report

FISCAL=ROOT/'config/fiscal/rules_2026.json'
CASE=ROOT/'data/fixtures/investment_case_example.json'


def _fixture():
    return json.loads(CASE.read_text(encoding='utf-8'))


def _equity_position(id, qty, average_cost, reference_price, realization_date=None):
    result = {'position_id':id,'account_id':'SYNTHETIC_PRIMARY','name':id,
        'isin':'FR0000120628','asset_type':'EQUITY','sale_quantity':str(qty),
        'reference_unit_price_eur':str(reference_price),'quote_date':'2026-10-30',
        'venue':'XPAR','tax_cost_method':'BROKER_REPORTED_AVERAGE',
        'broker_tax_unit_cost_eur':str(average_cost),
        'lots':[{'lot_id':f'{id}-1','purchase_date':'2025-05-12','quantity':str(qty)}],
        'ftt_scope':'no','fx_bps':'0','spread_bps':'0'}
    if realization_date:
        result['realization_date']=realization_date
    return result


def _event(day, value, category='REDDITI_DIVERSI'):
    return {'realization_date':day,'category':category,'fiscal_event':'gain' if value>0 else 'loss',
            'compensable_eur':str(abs(value)), 'hypothetical_realized_net_eur':str(value),
            'tax_rate':'0.26','position_id':str(value)}


def test_same_day_gains_losses_reduce_wallet_offset_and_tax_saving():
    c=_fixture()
    c['existing_positions']=[_equity_position('GAIN',100,40,60),
                             _equity_position('LOSS',50,90,70)]
    r=evaluate_case(c,FiscalRegistry.load(FISCAL))['B_REALIZE_EXISTING']
    # Gain: 100*60 - 12 - 100*40 = +1988.00 ; loss: 50*70 - 7 - 50*90 = -1007
    assert r['gross_eligible_gains_eur']=='1988.00'
    assert r['gross_eligible_losses_eur']=='1007.00'
    assert r['same_year_losses_applied_eur']=='1007.00'
    assert r['eligible_net_gain_eur']=='981.00'
    assert r['wallet']['compensated_eur']=='981.00'
    assert r['wallet']['potential_tax_avoided_eur']=='255.06'
    assert r['estimated_income_tax_eur']=='0.00'


def test_loss_chronology_blocks_retrospective_offsets():
    wallets=[]
    events=[_event('2026-11-02',100),_event('2026-11-03',-80)]
    result=net_realizations(events,wallets,'SYNTHETIC_PRIMARY',2026)
    assert result['eligible_net_gain_eur']=='100.00'
    assert result['unused_current_year_loss_eur']=='80.00'
    assert result['estimated_income_tax_eur']=='26.00'
    # In the opposite chronology the earlier loss offsets the later gain.
    events=[_event('2026-11-02',-80),_event('2026-11-03',100)]
    result=net_realizations(events,wallets,'SYNTHETIC_PRIMARY',2026)
    assert result['eligible_net_gain_eur']=='20.00'
    assert result['estimated_income_tax_eur']=='5.20'


def test_etf_capital_gain_never_offsets_even_when_etf_loss_can():
    events=[_event('2026-11-02',-100),_event('2026-11-02',180),
            _event('2026-11-02',130,'REDDITI_CAPITALE')]
    x=net_realizations(events,[],'SYNTHETIC_PRIMARY',2026)
    assert x['eligible_net_gain_eur']=='80.00'
    assert x['estimated_capital_income_tax_eur']=='33.80'
    assert x['estimated_unoffset_different_tax_eur']=='20.80'


def test_existing_case_displays_income_tax_and_costs_not_only_tax_saving():
    result=evaluate_case(_fixture(),FiscalRegistry.load(FISCAL))
    b=result['B_REALIZE_EXISTING']
    assert b['estimated_capital_income_tax_eur']=='37.70'
    assert b['estimated_incremental_tax_and_execution_effect_eur']=='35.50'
    assert b['total_sale_execution_costs_eur']=='10.00'
    c=result['C_NEW_INVESTMENT']
    assert c['economic_profit_after_estimated_tax_eur']=='110.00'


def test_date_of_existing_quote_stale_or_future_is_rejected():
    reg=FiscalRegistry.load(FISCAL)
    for date_bad in ('2019-01-01','2026-11-03'):
        c=_fixture()
        c['existing_positions'][0]['quote_date']=date_bad
        with pytest.raises(ValueError,match='(Stale|Future) quotation'):
            evaluate_case(c,reg)


def test_tiny_share_breakeven_has_adaptive_upper_bound():
    fee=Fees()
    threshold=break_even_sell_unit_price(1,'1.00',fee,
        italy_ftt_status='no',fx_bps='0',spread_bps='0')
    # Buy 1 EUR + 5 fee, selling 1 share needs 6 EUR + 5 fee.
    assert threshold==Decimal('11.00')
    sale=trade_costs(1,threshold,fee,side='sell',
        italy_ftt_status='no',fx_bps='0',spread_bps='0')
    assert Decimal(sale['net_proceeds_eur'])>=Decimal('6.00')
    with pytest.raises(ValueError,match='Invalid FX'):
        trade_costs(1,100,fee,fx_bps='NaN')
    with pytest.raises(ValueError,match='Invalid spread'):
        trade_costs(1,100,fee,spread_bps=-1)


def test_ledger_annotations_survive_reruns_and_new_case(tmp_path):
    c=_fixture()
    saved=save_decision(tmp_path,c,FISCAL)
    record_human_decision(tmp_path,saved['decision_id'],'NO_ACTION',observed_outcome='MANUAL_NOTE')
    save_decision(tmp_path,c,FISCAL)
    doc=json.loads((tmp_path/'decision_comparison.json').read_text())
    assert doc['human_decision']=='NO_ACTION'
    assert doc['observed_outcome']=='MANUAL_NOTE'
    assert len((tmp_path/'decision_ledger.jsonl').read_text().splitlines())==2
    c['investment_budget_eur']='20001'
    save_decision(tmp_path,c,FISCAL)
    assert len((tmp_path/'decision_ledger.jsonl').read_text().splitlines())==3
    assert 'NO_ACTION' in (tmp_path/'decision_ledger.jsonl').read_text()


def test_user_case_local_cli_integration(tmp_path):
    c=_fixture()
    c['fixture_kind']=USER
    c['existing_positions']=[c['existing_positions'][1]]  # broker-reported average
    private=tmp_path/'portfolio_private.json'
    private.write_text(json.dumps(c),encoding='utf-8')
    out=tmp_path/'out'
    make_report(out,case_path=private)
    html_report(out)
    obj=json.loads((out/'decision_comparison.json').read_text())
    assert obj['mode']==USER
    assert 'NON VERIFICATO' in (out/'dashboard.html').read_text()
    assert 'fornito dall’utente' in (out/'DECISION_COMPARISON.md').read_text()


def test_index_overlap_snapshot_marks_both_candidates_and_unknown_is_flagged():
    from investresearch.cli import _source_rows
    inst,_=_source_rows()
    known={r['id']:r for r in inst}
    cfg={'avoid_duplicate_eurostoxx50':True}
    for symbol in ('AXA','SAN'):
        assert any(x.code=='overlap' for x in instrument_constraints(known[symbol],cfg))
    assert any(x.code=='overlap_unverified' for x in instrument_constraints(known['MSFT'],cfg))


def test_malformed_active_quote_is_explicitly_blocked():
    inst=[{'id':'TEST','isin':'FR0000120628','exchange':'Euronext Paris',
           'oil_exposure':'none','fiscal_status':'eligible'}]
    for bad in ('NaN','Infinity','not-a-number'):
        q=[{'id':'TEST','price':bad,'market_date':'2026-10-30','source_url':'https://example.org'}]
        assert any(x.gate=='quote' and x.severity=='BLOCKED' for x in audit(inst,q,date(2026,11,1)))


def test_same_netting_not_applied_to_unverified_etn():
    events=[_event('2026-11-02',100),_event('2026-11-02',500,'REVIEW_REQUIRED')]
    x=net_realizations(events,[],'SYNTHETIC_PRIMARY',2026)
    assert x['eligible_net_gain_eur']=='100.00'
    assert x['unresolved_tax_positions']
    assert x['fiscal_status']=='INCOMPLETE'


def test_break_even_property_across_sizes_and_spread_scenarios():
    import random
    random.seed(20261101)
    fee = Fees()
    for _ in range(120):
        qty = random.randint(1, 300)
        p = Decimal(str(round(random.uniform(.12,250),2)))
        spread = str(random.randint(0,250))
        fx = str(random.randint(0,50))
        opts={'italy_ftt_status':'no','fx_bps':fx,'spread_bps':spread}
        price = break_even_sell_unit_price(qty,p,fee,**opts)
        buy = trade_costs(qty,p,fee,side='buy',**opts)
        sell = trade_costs(qty,price,fee,side='sell',**opts)
        assert Decimal(sell['net_proceeds_eur']) >= Decimal(buy['outlay_eur'])


def test_netting_with_old_wallet_and_current_year_loss_first():
    wallets=[{'account_id':'SYNTHETIC_PRIMARY','tax_regime':'amministrato',
              'year':2022,'remaining_eur':'3300','verification_status':'DECLARED'}]
    result=net_realizations([_event('2026-11-02',-500),
                             _event('2026-11-03',700)],wallets,'SYNTHETIC_PRIMARY',2026)
    assert result['same_year_losses_applied_eur']=='500.00'
    assert result['wallet']['compensated_eur']=='200.00'
    assert result['wallet']['potential_tax_avoided_eur']=='52.00'
    assert result['wallet']['allocations']==[{'vintage':2022,'used_eur':'200.00'}]
    # No mutation of input wallet (repeatability).
    assert wallets[0]['remaining_eur']=='3300'


def test_declared_regime_is_not_silently_treated_as_administered():
    c = _fixture()
    c['tax_regime'] = 'dichiarativo'
    with pytest.raises(ValueError, match='only risparmio amministrato'):
        evaluate_case(c, FiscalRegistry.load(FISCAL))
    with pytest.raises(ValueError, match='only risparmio amministrato'):
        net_realizations([_event('2026-11-02', 100)], [], 'SYNTHETIC_PRIMARY', 2026,
                         regime='dichiarativo')


def test_hypothetical_realization_date_defaults_to_last_venue_session():
    c = _fixture()  # 1 November 2026 falls on a Sunday.
    result = evaluate_case(c, FiscalRegistry.load(FISCAL))
    for p in result['B_REALIZE_EXISTING']['positions']:
        assert p['realization_date'] == '2026-10-30'
        assert p['realization_date_provenance'] == 'HYPOTHETICAL_DEFAULT_LAST_VENUE_SESSION'
    assert result['C_NEW_INVESTMENT']['realization_date'] == '2026-10-30'
    assert result['C_NEW_INVESTMENT']['realization_date_provenance'] == 'HYPOTHETICAL_DEFAULT_LAST_VENUE_SESSION'
    # Even explicit hypothetical dates must correspond to a supported session.
    c['existing_positions'][0]['realization_date'] = '2026-11-01'
    with pytest.raises(ValueError, match='trading session'):
        evaluate_case(c, FiscalRegistry.load(FISCAL))
    c = _fixture()
    c['new_investment']['realization_date'] = '2026-11-01'
    with pytest.raises(ValueError, match='trading session'):
        evaluate_case(c, FiscalRegistry.load(FISCAL))
    c = _fixture()
    del c['new_investment']['venue']
    with pytest.raises(ValueError, match='requires a known venue'):
        evaluate_case(c, FiscalRegistry.load(FISCAL))


@pytest.mark.parametrize('bad_price', ['0', '-0.1', 'NaN', 'Infinity', '-Infinity'])
def test_quote_nonpositive_or_nonfinite_is_blocked(bad_price):
    inst = [{'id':'TEST','isin':'FR0000120628','exchange':'Euronext Paris',
             'fiscal_status':'eligible','oil_exposure':'none'}]
    quote = [{'id':'TEST','price':bad_price,'market_date':'2026-10-30',
              'source_url':'https://example.org','volume':'100'}]
    statuses = audit(inst, quote, date(2026, 11, 1))
    assert any(s.gate == 'quote' and s.severity == 'BLOCKED' for s in statuses)


@pytest.mark.parametrize('bad_volume', ['-1', 'NaN', 'Infinity', 'invalid'])
def test_supplied_bad_quote_volume_is_blocked(bad_volume):
    inst = [{'id':'TEST','isin':'FR0000120628','exchange':'Euronext Paris',
             'fiscal_status':'eligible','oil_exposure':'none'}]
    quote = [{'id':'TEST','price':'12.30','market_date':'2026-10-30',
              'source_url':'https://example.org','volume':bad_volume}]
    statuses = audit(inst, quote, date(2026, 11, 1))
    assert any(s.gate == 'volume' and s.severity == 'BLOCKED' for s in statuses)


def test_dashboard_handles_missing_scenarios_and_decision_gracefully(tmp_path):
    html_report(tmp_path)
    output = (tmp_path/'dashboard.html').read_text(encoding='utf-8')
    assert '<thead>' in output and '</thead>' in output
    assert '<tbody></tbody>' in output
    assert '<script' not in output
