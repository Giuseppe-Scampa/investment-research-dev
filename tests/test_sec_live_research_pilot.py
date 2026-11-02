"""Independently constructed SEC evidence payloads; never call the internet."""
import json
from datetime import date
from pathlib import Path

import pytest

from investresearch.research_sources import sha256_bytes, SEC_TICKERS_URL, SEC_HOST
from investresearch.research_sec_pilot import (
    analyze_sec_evidence, collect_sec_pilot, parse_symbols, write_sec_evidence,
)

ASOF = date(2026, 11, 2)


def _cached(tmp_path, provider, identifier, data, url, *, retrieved='2026-11-02T10:20:30+00:00'):
    raw = json.dumps(data, sort_keys=True).encode('utf-8')
    out = tmp_path / (identifier or 'catalog')
    out.write_bytes(raw)
    return dict(provider=provider, identifier=identifier, path=str(out),
                sha256=sha256_bytes(raw), source_url=url, retrieved_at_utc=retrieved)


def _catalog(tmp_path, *, entries=None):
    entries = entries or [[320193, 'Apple Inc', 'AAPL', 'Nasdaq'],
                          [789019, 'Microsoft Corp', 'MSFT', 'Nasdaq'],
                          [101, 'Legacy', 'OLD', 'UNSUPPORTED']]
    return _cached(tmp_path, 'SEC_TICKERS', '',
                   {'fields':['cik','name','ticker','exchange'], 'data':entries},SEC_TICKERS_URL)


def _filing(tmp_path, cik='0000320193', *, income=200, revenue=1000,
            rev_accn='0000320193-25-000010', inc_accn='0000320193-25-000010',
            extra=None):
    start='2024-09-29';end='2025-09-27'
    def row(value, accn):
        return dict(start=start,end=end,form='10-K',fp='FY',fy=2025, filed='2025-10-31',val=value,accn=accn)
    facts={'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':[row(revenue,rev_accn)]}},
           'NetIncomeLoss':{'units':{'USD':[row(income,inc_accn)]}}}
    if extra:
        facts['NetIncomeLoss']['units']['USD'].append(extra)
    return _cached(tmp_path, 'SEC_COMPANYFACTS', cik,
                    {'cik':int(cik),'facts':{'us-gaap':facts}}, SEC_HOST+f'CIK{cik}.json')


def test_parse_symbols_strict_and_bounded():
    assert parse_symbols(' aapl,msft,NVDA ') == ['AAPL','MSFT','NVDA']
    for bad in ['', 'AAPL,', 'AAPL,AAPL', 'AAPL;DROP', 'AAPL,../../x',
                ','.join('A'+str(i) for i in range(9))]:
        with pytest.raises(ValueError):parse_symbols(bad)


def test_companyfacts_current_filing_and_real_metadata(tmp_path):
    c=_catalog(tmp_path)
    f=_filing(tmp_path)
    result=analyze_sec_evidence(c, {'0000320193':f}, ['AAPL','MSFT','OLD','GHOST'],ASOF)
    assert result['catalog_record_count']==3
    assert result['annual_evidence_count']==1
    assert result['market_ranking_count']==0
    first=result['results'][0]
    assert first['revenue_usd']=='1000'
    assert first['net_income_usd']=='200'
    assert first['net_margin_pct']=='20.00'
    assert first['period_end']=='2025-09-27'
    assert first['filing_accession']=='0000320193-25-000010'
    assert result['results'][1]['status']=='COMPANYFACTS_NOT_ACQUIRED'
    assert result['results'][2]['status']=='UNSUPPORTED_VENUE'
    assert result['results'][3]['status']=='UNMAPPED_OR_AMBIGUOUS_TICKER'
    output=tmp_path/'results'
    exported=write_sec_evidence(result, output)
    assert exported['rows']==4
    assert (output/'SEC_ANNUAL_RESEARCH.csv').exists()
    assert (output/'SEC_ANNUAL_RESEARCH.md').exists()
    raw=(output/'SEC_ANNUAL_RESEARCH.json').read_text()
    assert 'research contact' not in raw
    assert str(tmp_path) not in raw
    assert 'NOT PRODUCED' in (output/'SEC_ANNUAL_RESEARCH.md').read_text()
    assert json.loads(raw)['market_ranking_count']==0


def test_source_hash_tampering_and_wrong_provider_fail_closed(tmp_path):
    c=_catalog(tmp_path)
    f=_filing(tmp_path)
    f['sha256']='0'*64
    with pytest.raises(ValueError, match='checksum'):
        analyze_sec_evidence(c, {'0000320193':f}, ['AAPL'],ASOF)
    f=_filing(tmp_path)
    f['source_url']='https://not-sec.gov/CIK0000320193.json'
    with pytest.raises(ValueError, match='source identity'):
        analyze_sec_evidence(c, {'0000320193':f}, ['AAPL'],ASOF)


def test_no_lookahead_acquisition_and_future_restatement(tmp_path):
    c=_catalog(tmp_path)
    with pytest.raises(ValueError, match='after as-of'):
        analyze_sec_evidence(dict(c, retrieved_at_utc='2026-11-03T00:00:00Z'), {}, ['AAPL'],ASOF)
    later=dict(start='2025-09-28',end='2026-09-26',form='10-K',fp='FY',fy=2026,
               filed='2026-11-09',val=99999,accn='0000320193-26-000010')
    f=_filing(tmp_path,extra=later)
    result=analyze_sec_evidence(c,{'0000320193':f},['AAPL'],ASOF)
    assert result['results'][0]['period_end']=='2025-09-27'
    assert result['results'][0]['net_income_usd']=='200'


def test_mixed_filing_not_misrepresented_as_reconciled(tmp_path):
    c=_catalog(tmp_path)
    f=_filing(tmp_path,inc_accn='0000320193-25-000099')
    result=analyze_sec_evidence(c,{'0000320193':f},['AAPL'],ASOF)
    assert result['annual_evidence_count']==0
    assert result['results'][0]['status']=='REVIEW_SEC_ANNUAL_FACTS_UNAVAILABLE'
    assert not result['results'][0]['net_margin_pct']


def test_wrong_company_id_rejected(tmp_path):
    c=_catalog(tmp_path)
    f=_filing(tmp_path,cik='00000789019')
    f['source_url']=SEC_HOST+'CIK0000320193.json'
    with pytest.raises(ValueError,match='CIK mismatch'):
        analyze_sec_evidence(c,{'0000320193':f},['AAPL'],ASOF)


def test_duplicate_ticker_catalog_not_silently_resolved(tmp_path):
    c=_catalog(tmp_path,entries=[[320193,'Apple Inc','AAPL','Nasdaq'],
                                 [87654,'Another Corp','AAPL','NYSE']])
    result=analyze_sec_evidence(c,{},['AAPL'],ASOF)
    assert result['results'][0]['status']=='UNMAPPED_OR_AMBIGUOUS_TICKER'


def test_negative_income_is_accepted_but_negative_revenue_reviewed(tmp_path):
    c=_catalog(tmp_path)
    f=_filing(tmp_path,income=-100)
    result=analyze_sec_evidence(c,{'0000320193':f},['AAPL'],ASOF)
    assert result['results'][0]['net_margin_pct']=='-10.00'
    f=_filing(tmp_path,revenue=-100)
    result=analyze_sec_evidence(c,{'0000320193':f},['AAPL'],ASOF)
    assert result['results'][0]['status']=='REVIEW_SEC_ANNUAL_FACTS_UNAVAILABLE'


def test_explicit_live_collection_is_bounded_by_selected_symbols(tmp_path):
    c=_catalog(tmp_path)
    f=_filing(tmp_path)
    current=date.today()
    c['retrieved_at_utc']=current.isoformat()+'T10:20:30+00:00'
    f['retrieved_at_utc']=current.isoformat()+'T10:20:30+00:00'
    calls=[];sleep=[]
    def fake_collect(provider, identifier, cache, sec_contact):
        calls.append((provider,identifier,sec_contact))
        if provider=='SEC_TICKERS':return c
        if provider=='SEC_COMPANYFACTS' and identifier=='0000320193':return f
        raise AssertionError('Unexpected request')
    result=collect_sec_pilot(['AAPL','OLD','GHOST'],current,tmp_path,'test@example.org',
                             collector=fake_collect,pause=sleep.append)
    assert calls==[('SEC_TICKERS','','test@example.org'),
                   ('SEC_COMPANYFACTS','0000320193','test@example.org')]
    assert sleep==[1.2]
    assert result['annual_evidence_count']==1


def test_offline_report_and_live_opt_in_cli(tmp_path):
    from investresearch.research_cli import main
    with pytest.raises(SystemExit):
        main(['sec-pilot','--symbols','AAPL','--cache',str(tmp_path)])
    with pytest.raises(ValueError, match="today's as-of"):
        main(['sec-pilot','--live-confirm','--symbols','AAPL','--as-of','2020-10-02',
              '--sec-contact','fake@example.org','--cache',str(tmp_path)])
