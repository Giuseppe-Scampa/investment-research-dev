"""Independent manually computed fiscal fixtures and end-to-end checks."""
import copy, csv, json, math
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from investresearch.market_calendar import session, session_age, settlement, trade_timeline
from investresearch.quality import read_strict_csv, validate_instrument_mapping, audit, readiness
from investresearch.constraints import instrument_constraints, portfolio_constraints
from investresearch.analytics import returns, indicators, wilder_rsi, eur_adjusted_returns
from investresearch.tax_engine import FiscalRegistry, classify_realization, wallet_offset, expired_potential
from investresearch.positions import sale_cost_basis, local_to_eur
from investresearch.cost_engine import affordable_units, break_even_sell_unit_price, trade_costs
from investresearch.core import Fees
from investresearch.cli import ROOT, make_report
from investresearch.dashboard import html_report, badge

REGISTRY = ROOT/'config/fiscal/rules_2026.json'
CASE = ROOT/'data/fixtures/investment_case_example.json'


def test_duplicate_quote_reader_fails(tmp_path):
    p=tmp_path/'dupes.csv'
    p.write_text('id,price\nAXA,1\nAXA,999\n', encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate ID'):
        read_strict_csv(p)


def test_ambiguous_listing_and_multivenue_allowed():
    one={'id':'A', 'isin':'FR0000120628','ticker':'CS.PA','exchange':'Euronext Paris', 'trade_currency':'EUR'}
    duplicate=dict(one,id='B',ticker='CS2.PA')
    with pytest.raises(ValueError,match='Ambiguous'):
        validate_instrument_mapping([one,duplicate])
    other=dict(one,id='C',ticker='CS.XETR',exchange='Xetra')
    assert validate_instrument_mapping([one,other])


def test_constraints_hard_vs_soft():
    settings={'exclude_primary_oil':True,'exclude_additional_gold':True,
              'avoid_duplicate_eurostoxx50':True,'max_positions':3,'preferred_positions':2}
    assert 'oil' in {x.code for x in instrument_constraints({'oil_exposure':'direct'},settings)}
    assert 'gold' in {x.code for x in instrument_constraints({'name':'Gold ETC','sector':'gold'},settings)}
    assert not instrument_constraints({'name':'Goldman Sachs','sector':'Financials'},settings)
    euro={'index_memberships':['EURO_STOXX_50'],'name':'AXA'}
    x=instrument_constraints(euro,settings)
    assert len(x)==1 and x[0].level=='REVIEW'
    assert portfolio_constraints({'A':1,'B':1,'C':1},0,settings)[0].level=='REVIEW'
    assert portfolio_constraints({'A':1,'B':1,'C':1,'D':1},0,settings)[0].level=='BLOCKED'


def test_exchange_sessions_and_settlement_fiscal_date_unknown():
    assert session(date(2026,10,30),'XMIL')
    assert not session(date(2026,12,24),'XMIL')
    assert not session(date(2026,12,25),'TARGET')
    assert session(date(2026,12,24),'TARGET')
    assert session_age(date(2026,11,1),date(2026,10,30),'XMIL')==0
    assert session_age(date(2026,11,4),date(2026,10,30),'XMIL')==3
    timeline=trade_timeline(date(2026,12,23),'XMIL',2)
    assert timeline['settlement_date']=='2026-12-28'
    assert timeline['fiscal_recognition_date'] is None
    with pytest.raises(ValueError):
        settlement(date(2026,12,24),2,'XMIL')
    with pytest.raises(ValueError):
        settlement(date(2026,12,30),2,'XMIL')


def test_finite_input_guards_and_wilder_rsi():
    for bad in [float('nan'),float('inf'),float('-inf'),-1,0]:
        with pytest.raises(ValueError):
            returns([100,bad])
    assert indicators([])['rsi_14'] is None
    # Wilder reference: strictly increasing 15 values => RSI = 100.
    assert wilder_rsi(list(range(1,16)))==100
    assert wilder_rsi([100]*15)==50
    # A flat tail must not instantly forget gains from the Wilder smoothed state.
    x=wilder_rsi([100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,114,114])
    assert x==100
    with pytest.raises(ValueError,match='non-synchronous'):
        eur_adjusted_returns({'2026-10-30':100},{'2026-10-29':1})


def test_tax_etf_gain_and_loss_not_symmetric():
    rule=FiscalRegistry.load(REGISTRY).get('ETF_UCITS',date(2026,11,1))
    gain=classify_realization(1100,900,rule)
    loss=classify_realization(800,900,rule)
    assert gain['category']=='REDDITI_CAPITALE' and gain['compensable_eur']=='0.00'
    assert loss['category']=='REDDITI_DIVERSI' and loss['compensable_eur']=='100.00'
    assert rule.category('periodic')=='REDDITI_CAPITALE'


def test_government_bond_ratio_manually_calculated():
    rule=FiscalRegistry.load(REGISTRY).get('ITALIAN_GOVT_BOND',date(2026,11,1))
    gain=classify_realization(11000,10000,rule)
    assert gain['compensable_eur']=='480.80'
    assert rule.tax_rate==Decimal('.26')
    assert Decimal(gain['compensable_eur'])*rule.tax_rate==Decimal('125.0080')
    assert rule.category('periodic')=='REDDITI_CAPITALE'


def test_unverified_etn_refuses_fiscal_eligibility():
    rule=FiscalRegistry.load(REGISTRY).get('ETN',date(2026,11,1),'XS2427355958')
    result=classify_realization(1100,1000,rule)
    assert result['category']=='REVIEW_REQUIRED'
    assert result['compensable_eur']=='0.00'
    with pytest.raises(ValueError):
        FiscalRegistry.load(REGISTRY).get('EQUITY',date(2027,1,1))


def test_wallet_expiry_partial_different_accounts():
    wallets=[{'account_id':'A','tax_regime':'amministrato','year':2022,'remaining_eur':'3200','verification_status':'DECLARED'},
             {'account_id':'B','tax_regime':'amministrato','year':2022,'remaining_eur':'4100','verification_status':'DECLARED'},
             {'account_id':'A','tax_regime':'amministrato','year':2020,'remaining_eur':'999','verification_status':'DECLARED'}]
    x=wallet_offset(wallets,1200,'A',2026)
    assert x['compensated_eur']=='1200.00' and x['potential_tax_avoided_eur']=='312.00'
    assert len(x['allocations'])==1 and x['allocations'][0]['vintage']==2022
    assert wallet_offset(wallets,6000,'A',2026)['uncompensated_eur']=='2800.00'
    assert wallet_offset(wallets,6000,'A',2027)['compensated_eur']=='0.00'
    assert len(expired_potential(wallets,2026))==2


def test_lots_no_assumed_fifo():
    p={'tax_cost_method':'EXPLICIT_LOT_SELECTION',
       'lots':[{'lot_id':'L1','quantity':'10','tax_unit_cost_eur':'70'},
               {'lot_id':'L2','quantity':'10','tax_unit_cost_eur':'85'}],
       'sale_lot_allocations':[{'lot_id':'L1','quantity':'5'},{'lot_id':'L2','quantity':'5'}]}
    assert sale_cost_basis(p,10)==(Decimal('775.00'),'ILLUSTRATIVE_SELECTED_LOTS_NOT_BROKER_METHOD')
    with pytest.raises(ValueError):sale_cost_basis(dict(p,tax_cost_method='FIFO'),10)
    with pytest.raises(ValueError):sale_cost_basis(dict(p,sale_lot_allocations=[{'lot_id':'L1','quantity':'9'}]),10)


def test_cash_reconciliation_and_break_even():
    fee=Fees()
    assert affordable_units(2130,42.60,fee,italy_ftt_status='no',fx_bps=0,spread_bps=0)==49
    buy=trade_costs(50,42.60,fee,italy_ftt_status='no',fx_bps=0,spread_bps=0)
    assert Decimal(buy['outlay_eur'])>2130
    breakeven=break_even_sell_unit_price(50,42.60,fee,italy_ftt_status='no',fx_bps=0,spread_bps=0)
    sale=trade_costs(50,breakeven,fee,side='sell',italy_ftt_status='no',fx_bps=0,spread_bps=0)
    assert Decimal(sale['net_proceeds_eur'])>=Decimal(buy['outlay_eur'])


def test_malformed_quote_blocked_and_per_stage_status():
    inst=[{'id':'AXA','isin':'FR0000120628','exchange':'Euronext Paris','fiscal_status':'eligible','oil_exposure':'none'}]
    q=[{'id':'AXA','price':'NaN','market_date':'2026-10-30','source_url':'https://example.org'}]
    status=audit(inst,q,date(2026,11,1))
    assert any(s.gate=='quote' and s.severity=='BLOCKED' for s in status)
    assert readiness(status,'AXA')['research_readiness']=='BLOCKED'
    q[0]['price']='42.60'
    ok=audit(inst,q,date(2026,11,1))
    assert readiness(ok,'AXA')['research_readiness']=='VERIFIED'
    assert readiness(ok,'AXA')['pretrade_readiness']=='INCOMPLETE'


def test_badges_nonverified_are_not_green():
    for marker in ['INCOMPLETE','ESTIMATED','HYPOTHETICAL','REVIEW','UNVERIFIED']:
        assert 'verified' not in badge(marker)
        assert 'pending' in badge(marker)
    assert 'verified' in badge('VERIFIED')


def test_end_to_end_deterministic_and_demo_label(tmp_path):
    make_report(tmp_path)
    html_report(tmp_path)
    names=['REPORT.md','DECISION_COMPARISON.md','decision_comparison.json','decision_ledger.json','dashboard.html']
    once={x:(tmp_path/x).read_bytes() for x in names}
    make_report(tmp_path)
    html_report(tmp_path)
    assert once=={x:(tmp_path/x).read_bytes() for x in names}
    a=json.loads((tmp_path/'decision_comparison.json').read_text())
    assert a['mode']=='SYNTHETIC_DEMONSTRATION_NOT_PERSONAL_HOLDINGS'
    assert a['B_REALIZE_EXISTING']['eligible_net_gain_eur']=='320.00'
    assert a['C_NEW_INVESTMENT']['wallet']['potential_tax_avoided_eur']=='28.60'
    assert a['human_decision'] is None and a['observed_outcome'] is None
    assert '<script' not in (tmp_path/'dashboard.html').read_text()
    assert (tmp_path/'quality_gates.json').exists()


def test_fx_and_cost_basis_documented():
    assert local_to_eur('80','0.91')==Decimal('72.80')
    with pytest.raises(ValueError):local_to_eur('80','NaN')
    with pytest.raises(ValueError):local_to_eur('80',0)
    lots={'tax_cost_method':'BROKER_REPORTED_AVERAGE','broker_tax_unit_cost_eur':'87.50',
          'lots':[{'lot_id':'1','quantity':'5','purchase_date':'2025-05-02'},
                  {'lot_id':'2','quantity':'5','purchase_date':'2026-01-02'}]}
    assert sale_cost_basis(lots,4)==(Decimal('350.00'),'BROKER_REPORTED_AVERAGE')
    lots['lots'][0]['purchase_date']='bad'
    with pytest.raises(ValueError,match='purchase date'):sale_cost_basis(lots,4)
