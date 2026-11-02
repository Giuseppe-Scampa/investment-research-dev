"""SEC research cohort, comparable FY growth and non-ranking safeguards."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from decimal import Decimal
import pytest
from investresearch.research_sources import parse_sec_annual_comparison, parse_sec_fundamentals
from investresearch.research_sec_pilot import (
    MAX_SYMBOLS, MAX_ANNUAL_AGE_DAYS, parse_symbols, analyze_sec_evidence,
    write_sec_evidence, collect_sec_pilot,
)
from investresearch.research_sources import SEC_HOST, SEC_TICKERS_URL, sha256_bytes

ASOF = date(2026, 11, 2)
ACC = '0000320193-26-000100'

def facts(*, prior_accession=ACC, prior_filed='2026-10-30', earlier_revenue=400,
          earlier_net_income=50, previous_included=True, negative_prior_income=False,
          latest_end='2026-09-26'):
    def row(start, end, val, acc, filed='2026-10-30'):
        return {'start':start,'end':end,'val':val,'filed':filed,'fp':'FY',
                'form':'10-K','accn':acc}
    rev=[row('2025-09-28',latest_end,500,ACC)]
    inc=[row('2025-09-28',latest_end,80,ACC)]
    if previous_included:
        rev.append(row('2024-09-29','2025-09-27',earlier_revenue,prior_accession,prior_filed))
        inc.append(row('2024-09-29','2025-09-27',-10 if negative_prior_income else earlier_net_income,prior_accession,prior_filed))
    return json.dumps({'cik':320193,'facts':{'us-gaap':{
        'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':rev}},
        'NetIncomeLoss':{'units':{'USD':inc}},
    }}}).encode()


def _meta(tmp_path,provider,payload,identifier='',url='',retrieved='2026-11-02T10:20:00+00:00'):
    name=(identifier or 'catalog')+'.bin'
    path=tmp_path/name
    path.write_bytes(payload)
    return {'provider':provider,'identifier':identifier,'source_url':url,
            'path':str(path),'sha256':sha256_bytes(payload),'retrieved_at_utc':retrieved}


def _catalog(tmp_path):
    body=json.dumps({'fields':['cik','name','ticker','exchange'],
                     'data':[[320193,'Apple Incorporated','AAPL','Nasdaq']]}).encode()
    return _meta(tmp_path,'SEC_TICKERS',body,url=SEC_TICKERS_URL)


def test_cohort_selection_supports_24_only_and_has_explicit_18_example():
    assert MAX_SYMBOLS==24
    assert len(parse_symbols(','.join('F'+str(n) for n in range(24))))==24
    with pytest.raises(ValueError,match='between 1 and 24'):
        parse_symbols(','.join('F'+str(n) for n in range(25)))
    path=Path(__file__).parents[1]/'config/sec_cohort_example.json'
    group=json.loads(path.read_text(encoding='utf-8'))
    chosen=parse_symbols(','.join(group['symbols']))
    assert len(chosen)==18 and chosen[0]=='AAPL' and len(set(chosen))==18
    assert 'NON_RANKED' in group['mode']


def test_growth_only_same_filing_same_concepts_and_year():
    body=facts()
    latest=parse_sec_fundamentals(body,ASOF)
    assert latest['revenue_usd']=='500' and latest['net_income_usd']=='80'
    comparison=parse_sec_annual_comparison(body,ASOF,latest)
    assert comparison['status']=='COMPARABLE_SAME_SEC_FILING'
    assert comparison['previous_period_end']=='2025-09-27'
    assert comparison['revenue_yoy_pct']=='25.00'
    assert comparison['net_income_yoy_pct']=='60.00'
    assert comparison['net_margin_change_pp']=='3.50'  # 16.0% - 12.5%
    assert comparison['source_filing_accession']==ACC


def test_no_comparison_when_prior_filing_is_different_or_after_asof():
    for body in (facts(prior_accession='0000320193-25-000001'),
                 facts(prior_filed='2026-11-05'), facts(previous_included=False)):
        latest=parse_sec_fundamentals(body,ASOF)
        comparison=parse_sec_annual_comparison(body,ASOF,latest)
        assert comparison['status']=='PRIOR_FY_NOT_COMPARABLE_SAME_FILING'
        assert 'revenue_yoy_pct' not in comparison


def test_negative_previous_income_suppresses_misleading_growth():
    body=facts(negative_prior_income=True)
    latest=parse_sec_fundamentals(body,ASOF)
    comparison=parse_sec_annual_comparison(body,ASOF,latest)
    assert comparison['status']=='COMPARABLE_SAME_SEC_FILING'
    assert comparison['net_income_yoy_pct'] is None
    assert comparison['net_income_change_usd']=='90'


def test_conflicting_competitor_observations_stop_comparison():
    obj=json.loads(facts()); units=obj['facts']['us-gaap']['NetIncomeLoss']['units']['USD']
    units.append(dict(units[1], val=72))
    body=json.dumps(obj).encode()
    latest=parse_sec_fundamentals(body,ASOF)
    assert parse_sec_annual_comparison(body,ASOF,latest)['status']=='CONFLICTING_PRIOR_FY_FACTS'


def test_pilot_emits_growth_staleness_and_no_trading_rank(tmp_path):
    catalog=_catalog(tmp_path)
    filing=_meta(tmp_path,'SEC_COMPANYFACTS',facts(),'0000320193',SEC_HOST+'CIK0000320193.json')
    result=analyze_sec_evidence(catalog,{'0000320193':filing},['AAPL'],ASOF)
    assert result['annual_evidence_count']==1
    assert result['comparable_prior_year_count']==1
    assert result['stale_annual_count']==0
    assert result['market_ranking_count']==0
    row=result['results'][0]
    assert row['net_margin_pct']=='16.00'
    assert row['previous_net_income_usd']=='50'
    assert row['net_margin_change_pp']=='3.50'
    output=tmp_path/'summary'
    write_sec_evidence(result,output)
    assert '25.00' in (output/'SEC_ANNUAL_RESEARCH.csv').read_text()
    assert 'NOT PRODUCED' in (output/'SEC_ANNUAL_RESEARCH.md').read_text()
    assert str(tmp_path) not in (output/'SEC_ANNUAL_RESEARCH.json').read_text()


def test_stale_annual_report_does_not_count_as_fresh_evidence(tmp_path):
    catalog=_catalog(tmp_path)
    obj=json.loads(facts());
    for label in ('RevenueFromContractWithCustomerExcludingAssessedTax','NetIncomeLoss'):
        for row in obj['facts']['us-gaap'][label]['units']['USD']:
            row['start']='2023-10-01';row['end']='2024-09-28';row['filed']='2024-10-31';row['accn']='0000320193-24-000100'
    filing=_meta(tmp_path,'SEC_COMPANYFACTS',json.dumps(obj).encode(),'0000320193',SEC_HOST+'CIK0000320193.json')
    result=analyze_sec_evidence(catalog,{'0000320193':filing},['AAPL'],ASOF)
    assert result['annual_evidence_count']==0
    assert result['stale_annual_count']==1
    assert result['results'][0]['annual_age_days']>MAX_ANNUAL_AGE_DAYS
    assert result['results'][0]['status']=='SEC_ANNUAL_STALE_REVIEW_NO_MARKET_RANK'


def test_pilot_no_unbounded_requests_and_deduplicates_cik(tmp_path):
    # Two different tickers with the same issuer CIK should only require one facts request.
    catalog_obj={'fields':['cik','name','ticker','exchange'],
                 'data':[[320193,'Apple','AAPL','Nasdaq'],[320193,'Apple Cl B','APLB','NYSE']]}
    catalog=_meta(tmp_path,'SEC_TICKERS',json.dumps(catalog_obj).encode(),url=SEC_TICKERS_URL,
                  retrieved=date.today().isoformat()+'T12:00:00+00:00')
    filing=_meta(tmp_path,'SEC_COMPANYFACTS',facts(),'0000320193',SEC_HOST+'CIK0000320193.json',
                 retrieved=date.today().isoformat()+'T12:00:00+00:00')
    calls=[]; sleeps=[]
    def collector(provider, identifier, cache, sec_contact):
        calls.append((provider,identifier))
        if provider=='SEC_TICKERS':return catalog
        assert identifier=='0000320193'
        return filing
    result=collect_sec_pilot(['AAPL','APLB'],date.today(),tmp_path,'research@example.org',
                             collector=collector,pause=sleeps.append)
    assert calls==[('SEC_TICKERS',''),('SEC_COMPANYFACTS','0000320193')]
    assert sleeps==[1.2]
    assert result['selected_count']==2


def test_sec_pilot_cohort_cli_accepts_file_without_network(monkeypatch,tmp_path):
    import investresearch.research_sec_pilot as pilot
    from investresearch.research_cli import main
    path=tmp_path/'cohort.json';path.write_text(json.dumps({'symbols':['AAPL','MSFT','NVDA']}))
    seen={}
    def fake(*args,**kwargs):
        seen['symbols']=args[0]
        return {'selected_count':3}
    monkeypatch.setattr(pilot,'collect_sec_pilot',fake)
    monkeypatch.setattr(pilot,'write_sec_evidence',lambda report,out:{'rows':3,'annual_evidence_count':0})
    main(['sec-pilot','--cohort',str(path),'--live-confirm','--sec-contact','test@example.org',
          '--output',str(tmp_path/'output')])
    assert seen['symbols']==['AAPL','MSFT','NVDA']
    path.write_text(json.dumps({'symbols':[12]}))
    with pytest.raises(SystemExit):
        main(['sec-pilot','--cohort',str(path),'--live-confirm','--sec-contact','test@example.org'])


def test_stale_same_filing_comparison_does_not_inflate_usable_comparable_count(tmp_path):
    catalog=_catalog(tmp_path)
    obj=json.loads(facts())
    for label in ('RevenueFromContractWithCustomerExcludingAssessedTax','NetIncomeLoss'):
        rows=obj['facts']['us-gaap'][label]['units']['USD']
        rows[0].update(start='2023-10-01',end='2024-09-28',filed='2024-10-31',accn='0000320193-24-000100')
        rows[1].update(start='2022-10-02',end='2023-09-30',filed='2024-10-31',accn='0000320193-24-000100')
    filing=_meta(tmp_path,'SEC_COMPANYFACTS',json.dumps(obj).encode(),
                 '0000320193',SEC_HOST+'CIK0000320193.json')
    result=analyze_sec_evidence(catalog,{'0000320193':filing},['AAPL'],ASOF)
    assert result['annual_evidence_count']==0
    assert result['stale_annual_count']==1
    assert result['results'][0]['comparison_status']=='COMPARABLE_SAME_SEC_FILING'
    assert result['comparable_prior_year_count']==0


def test_sec_profitloss_annual_fallback_is_disclosed_and_comparable(tmp_path):
    obj=json.loads(facts())
    us=obj['facts']['us-gaap']
    income=us.pop('NetIncomeLoss')
    us['ProfitLoss']=income
    body=json.dumps(obj).encode()
    latest=parse_sec_fundamentals(body,ASOF)
    assert latest['earnings_concept']=='ProfitLoss'
    assert latest['earnings_basis']=='CONSOLIDATED_PROFIT_LOSS_INCLUDING_NONCONTROLLING_INTERESTS'
    comparison=parse_sec_annual_comparison(body,ASOF,latest)
    assert comparison['status']=='COMPARABLE_SAME_SEC_FILING'
    catalog=_catalog(tmp_path)
    filing=_meta(tmp_path,'SEC_COMPANYFACTS',body,'0000320193',SEC_HOST+'CIK0000320193.json')
    report=analyze_sec_evidence(catalog,{'0000320193':filing},['AAPL'],ASOF)
    row=report['results'][0]
    assert report['annual_evidence_count']==1
    assert row['earnings_concept']=='ProfitLoss'
    assert 'NONCONTROLLING' in row['earnings_basis']
    assert row['revenue_yoy_pct']=='25.00'


def test_netincomeloss_preferred_when_both_profit_concepts_present():
    obj=json.loads(facts())
    us=obj['facts']['us-gaap']
    us['ProfitLoss']={'units':{'USD':[dict(us['NetIncomeLoss']['units']['USD'][0],val=999)]}}
    latest=parse_sec_fundamentals(json.dumps(obj).encode(),ASOF)
    assert latest['earnings_concept']=='NetIncomeLoss'
    assert latest['net_income_usd']=='80'
