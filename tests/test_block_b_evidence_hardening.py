"""Independent Block B tests for external evidence and score gates (no network)."""
from __future__ import annotations
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from investresearch.research_sources import (SEC_TICKERS_URL, source_request,
    collect, parse_sec_fundamentals, sha256_bytes)
from investresearch.research_universe import parse_sec_tickers, write_sec_candidates
from investresearch.research_screen import _history_quality, _point_in_time_source_status, screen
from investresearch.demo_dataset import create
from investresearch.research_bundle import EXTERNAL, build_bundle


def _catalog():
    return json.dumps({'fields':['cik','name','ticker','exchange'],'data':[
        [320193,'Apple Inc','AAPL','Nasdaq'],
        [789019,'Microsoft Corp','MSFT','Nasdaq'],
        [19617,'JPMorgan Chase & Co','JPM','NYSE'],
        [999,'Unlisted Example','UNL','OTC']]}).encode()


def test_official_sec_universe_parsing_and_as_of(tmp_path):
    with pytest.raises(ValueError,match='contact'):
        source_request('SEC_TICKERS')
    request,url=source_request('SEC_TICKERS',sec_contact='owner@example.org')
    assert url==SEC_TICKERS_URL
    assert request.get_header('User-agent').endswith('owner@example.org')
    with pytest.raises(ValueError,match='no identifier'):
        source_request('SEC_TICKERS','AAPL',sec_contact='owner@example.org')
    rows=parse_sec_tickers(_catalog())
    assert len(rows)==4 and rows[0]['venue']=='XNAS'
    raw=tmp_path/'raw.bin';raw.write_bytes(_catalog())
    meta=tmp_path/'meta.json';meta.write_text(json.dumps({'provider':'SEC_TICKERS',
        'source_url':SEC_TICKERS_URL,'sha256':sha256_bytes(_catalog()),
        'retrieved_at_utc':'2026-11-01T12:00:00+00:00'}))
    res=write_sec_candidates(raw,meta,date(2026,11,2),tmp_path/'catalog',limit=2)
    assert res['candidate_count']==2 and res['total_sec_records']==4
    assert res['mapped_exchange_records']==3
    assert res['mode']=='DISCOVERY_ONLY_UNRANKED'
    csv=(tmp_path/'catalog/SEC_CANDIDATES.csv').read_text()
    assert 'AAPL' in csv and 'JPM' in csv and 'MSFT' not in csv
    assert 'MISSING_SECTOR_ISIN_PRICES' in csv
    with pytest.raises(ValueError,match='look-ahead'):
        write_sec_candidates(raw,meta,date(2026,10,31),tmp_path/'bad')
    raw.write_bytes(_catalog()+b' ')
    with pytest.raises(ValueError,match='matching official'):
        write_sec_candidates(raw,meta,date(2026,11,2),tmp_path/'bad')


def test_sec_catalog_rejects_injected_duplicates_and_wrong_schema():
    with pytest.raises(ValueError,match='schema'):
        parse_sec_tickers(b'{"fields":["ticker"],"data":[]}')
    rows=json.loads(_catalog());rows['data'].append([888,'Copy','AAPL','Nasdaq'])
    with pytest.raises(ValueError,match='Duplicate'):
        parse_sec_tickers(json.dumps(rows).encode())


def test_sec_companyfacts_revenue_income_must_share_filing_accession():
    def item(val, accession, filed):
        return {'form':'10-K','fp':'FY','start':'2025-01-01','end':'2025-12-31',
                'filed':filed,'accn':accession,'val':val}
    facts={'facts':{'us-gaap':{
        'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':[
            item(1000,'0000000000-26-000010','2026-02-01'),
            item(8000,'0000000000-26-000011','2026-02-07')]}},
        'NetIncomeLoss':{'units':{'USD':[
            item(200,'0000000000-26-000010','2026-02-01')]}}}}}
    result=parse_sec_fundamentals(json.dumps(facts).encode(),date(2026,11,2))
    assert result['revenue_usd']=='1000' and result['net_income_usd']=='200'
    assert result['source_filing_accession']=='0000000000-26-000010'
    facts['facts']['us-gaap']['NetIncomeLoss']['units']['USD'][0]['accn']='0000000000-26-000012'
    with pytest.raises(ValueError,match='same-filing'):
        parse_sec_fundamentals(json.dumps(facts).encode(),date(2026,11,2))


def test_history_gate_detects_missing_sessions_and_extreme_moves():
    from investresearch.demo_dataset import _days
    days=_days('XMIL')[-70:]
    data=[(str(d),Decimal('100')+Decimal(i)/100,Decimal(5000)) for i,d in enumerate(days)]
    assert _history_quality(data,'XMIL')['verified']
    bad=data[:];bad.pop(-30)
    result=_history_quality(bad,'XMIL')
    assert not result['verified'] and result['missing_sessions'] == 1
    assert result['reason']=='MISSING_OR_INVALID_TRADING_SESSIONS'
    jump=data[:];jump[-5]=(jump[-5][0],jump[-5][1]*Decimal(2),jump[-5][2])
    assert _history_quality(jump,'XMIL')['reason']=='UNVERIFIED_CORPORATE_ACTION_OR_EXTREME_PRICE_JUMP'


def test_full_screen_no_rank_for_missing_bar_and_future_collection(tmp_path):
    create(tmp_path/'demo')
    p=tmp_path/'demo/prices/DEMO_GRID.csv'
    lines=p.read_text().splitlines()
    del lines[-12]
    p.write_text('\n'.join(lines)+'\n')
    m=json.loads((tmp_path/'demo/manifest.json').read_text())
    for a in m['assets']:
        if a['id']=='DEMO_GRID':
            a['prices']['sha256']=sha256_bytes(p.read_bytes())
    (tmp_path/'demo/manifest.json').write_text(json.dumps(m))
    result=screen(tmp_path/'demo')
    grid=next(r for r in result['results'] if r['id']=='DEMO_GRID')
    assert grid['market_score'] is None
    assert 'MISSING_OR_INVALID_TRADING_SESSIONS' in grid['warnings']

    meta={'mode':EXTERNAL}
    asset={'currency':'EUR','prices':{'retrieved_at_utc':'2026-11-03T10:00:00+00:00'}}
    assert _point_in_time_source_status(meta,asset,date(2026,11,2),None)==['SNAPSHOT_COLLECTED_AFTER_AS_OF']
    asset['prices']['retrieved_at_utc']='2026-11-02T09:00:00+00:00'
    assert _point_in_time_source_status(meta,asset,date(2026,11,2),None)==[]
    asset['prices'].pop('retrieved_at_utc')
    assert 'MISSING_SOURCE_COLLECTION_DATE' in _point_in_time_source_status(meta,asset,date(2026,11,2),None)


def test_ecb_xml_realistic_envelope_and_stale_provider_rejected(tmp_path):
    from investresearch.research_sources import parse_ecb
    import io
    xml=b'''<?xml version="1.0" encoding="UTF-8"?>
    <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
    xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
      <Cube><Cube time="2026-10-30"><Cube currency="USD" rate="1.16"/>
      <Cube currency="GBP" rate="0.86"/></Cube></Cube>
    </gesmes:Envelope>'''
    parsed=parse_ecb(xml,date(2026,11,2))
    assert parsed==[{'date':'2026-10-30','usd_per_eur':'1.16'}]
    with pytest.raises(ValueError,match='weekend'):
        parse_ecb(b'Date,USD\n2010-02-14,1.45\n',date(2026,11,2))
    old=b'Date,USD\n2010-02-15,1.45\n'
    class Fake(io.BytesIO):pass
    with pytest.raises(ValueError,match='stale'):
        collect('ECB_EUR_FX','',tmp_path,transport=lambda req,timeout:Fake(old))
