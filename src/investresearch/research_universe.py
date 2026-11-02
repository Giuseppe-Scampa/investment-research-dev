"""SEC-listed candidate discovery, distinct from verified research/ranking.

SEC's company_tickers_exchange.json is a *current* association snapshot, not a
point-in-time list of historical constituents, prices, sectors, or ISINs.
It can seed a broad US research universe, but must never imply a trade signal.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path
from .research_sources import MAX_BYTES, SEC_TICKERS_URL, sha256_bytes

EXCHANGES = {'Nasdaq':'XNAS','NYSE':'XNYS'}


def parse_sec_tickers(payload: bytes):
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError('Invalid SEC ticker payload length')
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get('fields') != ['cik', 'name', 'ticker', 'exchange'] or not isinstance(data.get('data'), list):
        raise ValueError('Unexpected SEC ticker exchange schema')
    result=[]; seen=set()
    for index, row in enumerate(data['data']):
        if not isinstance(row,list) or len(row)!=4:
            raise ValueError(f'Malformed SEC ticker record at {index}')
        cik,name,ticker,exchange=row
        if isinstance(cik,bool) or not isinstance(cik,int) or not 1<=cik<=9999999999:
            raise ValueError('Invalid SEC CIK')
        if not isinstance(name,str) or not isinstance(ticker,str) or not isinstance(exchange,str):
            raise ValueError('Invalid SEC ticker field')
        name=name.strip();ticker=ticker.strip();exchange=exchange.strip()
        if not name or not ticker or len(name)>300 or not ticker.isascii() or len(ticker)>25 or any(c.isspace() for c in ticker):
            raise ValueError('Malformed SEC company or ticker')
        key=(ticker.upper(),exchange.upper())
        if key in seen:
            raise ValueError(f'Duplicate SEC ticker listing: {ticker}/{exchange}')
        seen.add(key)
        result.append({'cik':str(cik).zfill(10),'name':name,'ticker':ticker,
                       'exchange':exchange,'venue':EXCHANGES.get(exchange, 'UNMAPPED')})
    if not result: raise ValueError('Empty SEC ticker universe')
    return sorted(result,key=lambda x:(x['ticker'],x['cik']))


def write_sec_candidates(raw_path:Path, metadata_path:Path, as_of:date, output:Path, *, limit=1000):
    """Generate an audit-ready, *unranked* US discovery catalog from cached bytes.

    Require a collection snapshot retrieved no later than as_of: current SEC
    associations cannot serve as a historical survivorship-free universe.
    """
    if not 1<=limit<=10000:raise ValueError('Universe limit must be between 1 and 10000')
    raw_path=Path(raw_path); metadata_path=Path(metadata_path)
    payload=raw_path.read_bytes()
    meta=json.loads(metadata_path.read_text(encoding='utf-8'))
    if meta.get('provider')!='SEC_TICKERS' or meta.get('source_url')!=SEC_TICKERS_URL or meta.get('sha256')!=sha256_bytes(payload):
        raise ValueError('SEC ticker raw data lacks matching official collection metadata')
    retrieved=date.fromisoformat(meta['retrieved_at_utc'][:10])
    if retrieved>as_of:
        raise ValueError('SEC ticker snapshot was retrieved after as_of; would introduce look-ahead')
    rows=parse_sec_tickers(payload)
    mapped=[r for r in rows if r['venue']!='UNMAPPED']
    chosen=mapped[:limit]
    for r in chosen:
        r['status']='CANDIDATE_ONLY_MISSING_SECTOR_ISIN_PRICES_AND_TAX_VERIFICATION'
        r['source_url']=SEC_TICKERS_URL
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    columns=['cik','name','ticker','exchange','venue','status','source_url']
    h=io.StringIO(newline='');writer=csv.DictWriter(h,fieldnames=columns,lineterminator='\n')
    writer.writeheader();writer.writerows(chosen)
    (output/'SEC_CANDIDATES.csv').write_text(h.getvalue(),encoding='utf-8')
    manifest={'as_of':as_of.isoformat(),'mode':'DISCOVERY_ONLY_UNRANKED','provider':'SEC_TICKERS',
              'source_url':SEC_TICKERS_URL,'raw_sha256':sha256_bytes(payload),
              'retrieved_at_utc':meta['retrieved_at_utc'],'total_sec_records':len(rows),
              'mapped_exchange_records':len(mapped),'candidate_limit':limit,
              'candidate_count':len(chosen),'candidate_csv_sha256':hashlib.sha256(h.getvalue().encode()).hexdigest(),
              'limitations':['Current ticker association data is not a survivorship-free historical universe',
                 'SEC list is US-only; global universe requires further documented listings',
                 'No ISIN, sector, ethical exposure, historical price, FX, fundamental or ranking is inferred']}
    (output/'SEC_CANDIDATES_MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return manifest
