"""Block B independent parser, provenance, as-of, and ranking regressions.

All inputs are synthetic. Network access is forbidden in the test suite.
"""
from __future__ import annotations
import copy
import csv
import hashlib
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from investresearch.research_sources import (source_request,collect,parse_stooq,
    parse_ecb,parse_sec_fundamentals,sha256_bytes)
from investresearch.research_bundle import (load_bundle,build_bundle,
    parse_normalized_prices,parse_normalized_fx,SYNTHETIC,EXTERNAL)
from investresearch.research_screen import screen,write_screening,_score_indicators,_fx_dated_prices
from investresearch.market_calendar import session
from investresearch.cli import ROOT

BUNDLE=ROOT/'data/research/demo'


def test_source_request_allowlist_and_credentials():
    with pytest.raises(ValueError,match='Unsupported'):
        source_request('ARBITRARY_URL','http://localhost:1')
    with pytest.raises(ValueError,match='contact'):
        source_request('SEC_COMPANYFACTS','12345')
    with pytest.raises(ValueError,match='CIK'):
        source_request('SEC_COMPANYFACTS','../bad',sec_contact='person@example.org')
    req,descriptor=source_request('SEC_COMPANYFACTS','320193',sec_contact='person@example.org')
    assert descriptor.endswith('CIK0000320193.json')
    assert req.get_header('User-agent').endswith('person@example.org')
    req,descriptor=source_request('ECB_EUR_FX')
    assert descriptor.endswith('eurofxref-hist.csv')
    with pytest.raises(ValueError,match='acknowledgement'):
        source_request('STOOQ_EOD_UNVERIFIED','aapl.us',stooq_key='free-demo')
    request,redacted=source_request('STOOQ_EOD_UNVERIFIED','aapl.us',stooq_key='private-free-key',acknowledge_stooq_terms=True)
    assert 'private-free-key' not in redacted
    assert 'private-free-key' in request.full_url


class _FakeResponse(io.BytesIO):
    pass


def test_collection_caches_immutable_hash_and_redacted_url(tmp_path):
    payload=b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,100,3000\n'
    def fake(req,timeout):
        assert timeout<=20
        return _FakeResponse(payload)
    result=collect('STOOQ_EOD_UNVERIFIED','aapl.us',tmp_path,
        stooq_key='mock-key',acknowledge_stooq_terms=True,transport=fake)
    assert result['sha256']==sha256_bytes(payload)
    assert Path(result['path']).read_bytes()==payload
    assert 'mock-key' not in json.dumps(result)
    second=collect('STOOQ_EOD_UNVERIFIED','aapl.us',tmp_path,
        stooq_key='mock-key',acknowledge_stooq_terms=True,transport=fake)
    assert second['sha256']==result['sha256'] and second['path']==result['path']
    Path(result['path']).write_bytes(b'evil')
    with pytest.raises(ValueError,match='collision|corruption'):
        collect('STOOQ_EOD_UNVERIFIED','aapl.us',tmp_path,
            stooq_key='mock-key',acknowledge_stooq_terms=True,transport=fake)


def test_collection_rejects_stooq_denial(tmp_path):
    with pytest.raises(ValueError,match='denial'):
        collect('STOOQ_EOD_UNVERIFIED','aapl.us',tmp_path,stooq_key='mock',acknowledge_stooq_terms=True,
            transport=lambda req,timeout:_FakeResponse(b'<html>quota exhausted</html>'))


def test_stooq_parser_strict_price_and_as_of():
    raw=b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,100,3000\n2026-11-05,100,101,99,100,4000\n'
    assert parse_stooq(raw,date(2026,11,1))==[{'date':'2026-10-30','close':'100','volume':'3000'}]
    for malformed in [
        b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,NaN,3000\n',
        b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,0,3000\n',
        b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,100,-1\n',
        b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,99,98,100,3000\n',
        b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,100,3000\n2026-10-30,99,102,98,100,3000\n',
    ]:
        with pytest.raises(ValueError):parse_stooq(malformed,date(2026,11,1))


def test_fx_ebc_parser_validation_and_future_filter():
    raw=b'Date, USD, GBP\n2026-10-30, 1.15, 0.9\n2026-11-05, 1.16, 0.8\n'
    assert parse_ecb(raw,date(2026,11,1))==[{'date':'2026-10-30','usd_per_eur':'1.15'}]
    with pytest.raises(ValueError,match='Invalid ECB'):
        parse_ecb(b'Date, USD\n2026-10-30, NaN\n',date(2026,11,1))
    with pytest.raises(ValueError,match='Duplicate ECB'):
        parse_ecb(b'Date, USD\n2026-10-30, 1.1\n2026-10-30, 1.2\n',date(2026,11,1))


def _sec_fixture(*, future=False, mismatched=False):
    def entry(val,filed,end='2025-12-31'):
        return {'form':'10-K','fp':'FY','start':'2025-01-01','end':end,'filed':filed,'val':val,'unit':'USD'}
    return json.dumps({'cik':320193,'facts':{'us-gaap':{
        'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':[
            entry(1000,'2026-02-02'),entry(9999,'2026-11-05'),entry(1100,'2026-02-02',end='2026-03-31')]}},
        'NetIncomeLoss':{'units':{'USD':[
            entry(200,'2026-02-02' if not mismatched else '2026-11-05'),
            entry(8888,'2026-11-05')]}}
        }}}).encode()


def test_sec_fundamentals_filters_future_restatement_and_mismatch():
    d=parse_sec_fundamentals(_sec_fixture(),date(2026,11,1))
    assert d['revenue_usd']=='1000' and d['net_income_usd']=='200'
    assert d['period_end']=='2025-12-31' and d['revenue_filed_date']=='2026-02-02'
    with pytest.raises(ValueError,match='same-period'):
        parse_sec_fundamentals(_sec_fixture(mismatched=True),date(2026,11,1))


def test_demo_bundle_metadata_and_scoring_are_consistent():
    manifest,items,fx,events=load_bundle(BUNDLE)
    assert manifest['mode']==SYNTHETIC and len(items)==7
    assert len(fx)>61 and len(events)==2
    report=screen(BUNDLE)
    assert report['universe_size']==7
    assert report['ranked_count']==5
    assert report['fundamentals_ranked_count']==3
    ranked=[r for r in report['results'] if r['market_score'] is not None]
    assert [r['market_rank'] for r in ranked]==list(range(1,6))
    assert all(r['trade_ready'] is False for r in report['results'])
    assert all('DEMO' in r['status'] for r in ranked)
    assert next(r for r in report['results'] if r['id']=='DEMO_OIL')['status']=='BLOCKED_BY_POLICY'
    assert next(r for r in report['results'] if r['id']=='DEMO_SHORT')['status']=='INCOMPLETE_NO_RANK'
    assert next(r for r in report['results'] if r['id']=='DEMO_ETF')['fundamental_metrics'] is None


def test_demo_fixture_regeneration_reproducible(tmp_path):
    from investresearch.demo_dataset import create
    create(tmp_path/'one');create(tmp_path/'two')
    a=(tmp_path/'one'/'manifest.json').read_bytes()
    b=(tmp_path/'two'/'manifest.json').read_bytes()
    assert a==b
    assert a==(BUNDLE/'manifest.json').read_bytes()


def test_bundle_hash_mismatch_and_path_escape_fail_closed(tmp_path):
    from investresearch.demo_dataset import create
    create(tmp_path/'demo')
    file=tmp_path/'demo/prices/DEMO_GRID.csv'
    file.write_text(file.read_text()+'tampered\n')
    with pytest.raises(ValueError,match='hash mismatch'):
        screen(tmp_path/'demo')
    create(tmp_path/'demo')
    m=json.loads((tmp_path/'demo/manifest.json').read_text())
    m['assets'][0]['prices']['path']='../../etc/passwd'
    (tmp_path/'demo/manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Unsafe'):
        load_bundle(tmp_path/'demo')


def test_as_of_security_no_future_history(tmp_path):
    raw=tmp_path/'raw.csv'
    raw.write_text('date,close,volume\n2026-10-30,30,100\n2026-11-02,3000,100\n')
    spec={'mode':SYNTHETIC,'as_of':'2026-11-01','assets':[{'id':'TEST','name':'test','venue':'XMIL',
        'currency':'EUR','sector':'Industry','oil_exposure':'none',
        'prices_source':{'provider':'SYNTHETIC_PRICES','path':str(raw)}}]}
    build_bundle(spec,tmp_path/'bundle')
    _,items,_,_=load_bundle(tmp_path/'bundle')
    assert len(items[0][1])==1 and items[0][1][0]['close']=='30'


def test_external_rejects_synthetic_inputs(tmp_path):
    raw=tmp_path/'raw.csv';raw.write_text('date,close,volume\n2026-10-30,30,100\n')
    spec={'mode':EXTERNAL,'as_of':'2026-11-01','assets':[{'id':'TEST','name':'test','venue':'XMIL',
        'currency':'EUR','sector':'Industry',
        'prices_source':{'provider':'SYNTHETIC_PRICES','path':str(raw)}}]}
    with pytest.raises(ValueError,match='Synthetic'):
        build_bundle(spec,tmp_path/'bundle')


def test_source_url_must_match_provider(tmp_path):
    raw=tmp_path/'stooq.csv';raw.write_text('Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,100,3000\n')
    spec={'mode':EXTERNAL,'as_of':'2026-11-01','assets':[{'id':'TEST','name':'test','venue':'XMIL',
        'currency':'EUR','sector':'Industry',
        'prices_source':{'provider':'STOOQ_EOD_UNVERIFIED','path':str(raw),
                         'source_url':'https://evil.example.org/not-stooq'}}]}
    with pytest.raises(ValueError,match='Stooq'):
        build_bundle(spec,tmp_path/'bundle')


def test_missing_fx_disables_currency_comparison():
    a=[{'date':'2026-10-30','close':'100','volume':'1000'}]
    vals,issue=_fx_dated_prices(a,None,'USD')
    assert issue=='MISSING_ECB_FX' and not vals
    vals,issue=_fx_dated_prices(a,[{'date':'2026-10-29','usd_per_eur':'1.1'}],'USD')
    assert issue=='LATEST_PRICE_HAS_NO_SAME_DAY_ECB_FX' and not vals
    vals,issue=_fx_dated_prices(a,[{'date':'2026-10-30','usd_per_eur':'1.25'}],'USD')
    assert issue is None and vals[0][1]==Decimal('80')


def test_market_score_no_rank_with_less_than_61_aligned_sessions():
    data=[(f'd{i}',Decimal(100+i),Decimal(200)) for i in range(60)]
    assert _score_indicators(data) is None
    data.append(('d60',Decimal('160'),Decimal('200')))
    m=_score_indicators(data)
    assert m['momentum_20']==round(160/140-1,7)
    assert m['aligned_observations']==61


def test_offline_report_is_byte_reproducible_and_safe(tmp_path):
    result=screen(BUNDLE)
    write_screening(result,tmp_path)
    contents={f.name:f.read_bytes() for f in tmp_path.iterdir()}
    write_screening(screen(BUNDLE),tmp_path)
    assert contents=={f.name:f.read_bytes() for f in tmp_path.iterdir()}
    h=(tmp_path/'block_b_dashboard.html').read_text()
    assert '<script' not in h
    assert 'NON' in h or 'non' in h
    assert 'DEMO_RANK_NOT_REAL_MARKET' in h
    parsed=json.loads((tmp_path/'BLOCK_B_SCREENING.json').read_text())
    assert parsed['dataset_manifest_sha256']==hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest()


def test_html_escapes_untrusted_instrument_name(tmp_path):
    from investresearch.demo_dataset import create
    create(tmp_path/'demo')
    m=json.loads((tmp_path/'demo/manifest.json').read_text())
    m['assets'][0]['name']='<img src=x onerror=alert(1)>'
    (tmp_path/'demo/manifest.json').write_text(json.dumps(m))
    write_screening(screen(tmp_path/'demo'),tmp_path/'out')
    html=(tmp_path/'out/block_b_dashboard.html').read_text()
    assert '&lt;img' in html and '<img' not in html


def test_bundled_demo_excludes_personal_data():
    raw=(BUNDLE/'manifest.json').read_text()
    for phrase in ('PERSONAL_ACCOUNT_NUMBER','BROKER_SECRET','OPENAI_API_KEY','PAYMENT_CARD'):
        assert phrase not in raw


def test_events_skip_unpublished_future_and_reject_duplicate():
    from investresearch.research_bundle import parse_events
    cols='event_id,asset_id,event_date,published_date,category,description,source_url\n'
    actual='E1,DEMO_GRID,2026-11-05,2026-10-30,earnings,Illustrative event,https://example.org/e1\n'
    future='E2,DEMO_GRID,2026-11-08,2026-11-06,policy,Unpublished,https://example.org/e2\n'
    events=parse_events((cols+actual+future).encode(),date(2026,11,1),synthetic=False)
    assert len(events)==1 and events[0]['event_id']=='E1'
    with pytest.raises(ValueError,match='Duplicate'):
        parse_events((cols+actual+actual).encode(),date(2026,11,1),synthetic=False)
    with pytest.raises(ValueError,match='source URL'):
        parse_events((cols+actual.replace('https://example.org/e1','')).encode(),date(2026,11,1),synthetic=False)


def test_stale_prices_are_never_ranked(tmp_path):
    from investresearch.demo_dataset import create
    create(tmp_path/'demo')
    m=json.loads((tmp_path/'demo/manifest.json').read_text())
    m['as_of']='2026-11-05'
    (tmp_path/'demo/manifest.json').write_text(json.dumps(m))
    report=screen(tmp_path/'demo')
    assert report['ranked_count']==0
    assert all(r['market_score'] is None for r in report['results'])
    assert any('STALE_BY_' in w for r in report['results'] for w in r['warnings'])


def test_unverified_index_membership_warns_but_does_not_hard_block(tmp_path):
    from investresearch.demo_dataset import create
    create(tmp_path/'demo')
    m=json.loads((tmp_path/'demo/manifest.json').read_text())
    m['assets'][0]['index_membership_status']='UNVERIFIED'
    (tmp_path/'demo/manifest.json').write_text(json.dumps(m))
    r=next(r for r in screen(tmp_path/'demo')['results'] if r['id']=='DEMO_GRID')
    assert r['market_score'] is not None
    assert 'overlap_unverified' in r['warnings']


def test_sec_bundle_rejects_mismatched_company_cik(tmp_path):
    sec=tmp_path/'companyfacts.json';sec.write_bytes(_sec_fixture())
    prices=tmp_path/'prices.csv'
    prices.write_bytes(b'Date,Open,High,Low,Close,Volume\n2026-10-30,99,102,98,100,10000\n')
    spec={'mode':EXTERNAL,'as_of':'2026-11-01','assets':[{
        'id':'APPLE_EXAMPLE','name':'test','asset_type':'EQUITY',
        'venue':'XNAS','currency':'USD','sec_cik':'0000123456',
        'prices_source':{'provider':'STOOQ_EOD_UNVERIFIED','path':str(prices),
                         'source_url':'https://stooq.com/q/d/l/?s=aapl.us&i=d&apikey=REDACTED'},
        'fundamentals_source':{'provider':'SEC_COMPANYFACTS','path':str(sec),
            'source_url':'https://data.sec.gov/api/xbrl/companyfacts/CIK0000123456.json'}
    }]}
    with pytest.raises(ValueError,match='CIK does not match'):
        build_bundle(spec,tmp_path/'bundle')


def test_external_market_dataset_not_trade_ready_even_if_ranked(tmp_path):
    raw=tmp_path/'synthetic_but_tagged_as_unverified_stooq.csv'
    from investresearch.demo_dataset import _days
    lines=['Date,Open,High,Low,Close,Volume']
    for i,d in enumerate(_days('XMIL')):
        p=100+i/10
        lines.append(f'{d},{p},{p+1},{p-1},{p},1000000')
    raw.write_text('\n'.join(lines)+'\n')
    spec={'mode':EXTERNAL,'as_of':'2026-11-01','assets':[{'id':'MOCK_REAL','name':'test','venue':'XMIL',
        'currency':'EUR','asset_type':'EQUITY','sector':'Industry','oil_exposure':'none',
        'prices_source':{'provider':'STOOQ_EOD_UNVERIFIED','path':str(raw),
            'source_url':'https://stooq.com/q/d/l/?s=test.it&i=d&apikey=REDACTED'}}]}
    build_bundle(spec,tmp_path/'external')
    result=screen(tmp_path/'external')
    assert result['ranked_count']==1
    item=result['results'][0]
    assert item['market_score'] is not None and not item['trade_ready']
    assert item['status']=='RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY'
