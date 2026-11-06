"""Point-in-time, hash-checked research datasets assembled from local source bytes.

Only an explicit `collect` call is allowed to use the network. The importer
never fetches links, and the screener never trusts unchecked file contents.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
from .research_sources import (MAX_BYTES, SEC_HOST, ECB_URL, ECB_CSV_URL, YAHOO_HISTORY_URL, YFINANCE, sha256_bytes, parse_ohlcv, parse_ecb,
                               parse_sec_fundamentals)
from .quality import valid_isin
from .research_fwb_local import PROVIDER as FWB_PERSONAL_HISTORY

SYNTHETIC = 'SYNTHETIC_DEMONSTRATION_NOT_MARKET_DATA'
EXTERNAL = 'EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE'
MANUAL_OHLCV = 'MANUAL_AUTHORIZED_LOCAL_OHLCV_UNVERIFIED'


def _positive(x, *, zero_ok=False):
    try: n=Decimal(str(x))
    except (InvalidOperation, TypeError) as exc: raise ValueError(f'Invalid numeric value: {x!r}') from exc
    if not n.is_finite() or n < 0 or (n == 0 and not zero_ok):
        raise ValueError(f'Expected positive finite number: {x!r}')
    return n


def parse_normalized_prices(payload: bytes, as_of: date):
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if reader.fieldnames != ['date','close','volume']:
        raise ValueError('Normalized price CSV must have date,close,volume columns')
    seen=set(); result=[]
    for r in reader:
        if None in r or any(v is None for v in r.values()):
            raise ValueError('Malformed price row')
        d=date.fromisoformat(r['date'])
        if d > as_of: continue
        if d in seen: raise ValueError('Duplicate session in prices')
        seen.add(d)
        result.append({'date':d.isoformat(),'close':str(_positive(r['close'])),
                       'volume':str(_positive(r['volume'],zero_ok=True))})
    if not result: raise ValueError('No usable point-in-time price history')
    return sorted(result,key=lambda x:x['date'])


def parse_normalized_fx(payload: bytes, as_of: date):
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if reader.fieldnames != ['date','usd_per_eur']:
        raise ValueError('Normalized FX CSV needs date,usd_per_eur')
    seen=set(); result=[]
    for r in reader:
        d=date.fromisoformat(r['date'])
        if d > as_of: continue
        if d in seen: raise ValueError('Duplicate FX date')
        seen.add(d)
        result.append({'date':d.isoformat(),'usd_per_eur':str(_positive(r['usd_per_eur']))})
    if not result: raise ValueError('No usable FX')
    return sorted(result,key=lambda x:x['date'])


def parse_synthetic_fundamentals(payload: bytes, as_of: date):
    d=json.loads(payload)
    if not isinstance(d,dict): raise ValueError('Fundamentals must be an object')
    for field in ('period_end','revenue_usd','net_income_usd','revenue_filed_date','earnings_filed_date'):
        if field not in d: raise ValueError(f'Missing fundamental field {field}')
    period=date.fromisoformat(d['period_end'])
    revfiled=date.fromisoformat(d['revenue_filed_date'])
    incfiled=date.fromisoformat(d['earnings_filed_date'])
    if period > revfiled or period > incfiled or revfiled > as_of or incfiled > as_of:
        raise ValueError('Fundamental not yet published as-of cutoff')
    if _positive(d['revenue_usd']) <= 0: raise ValueError('Revenue <=0')
    try: net=Decimal(str(d['net_income_usd']))
    except InvalidOperation as exc: raise ValueError('Invalid earnings') from exc
    if not net.is_finite(): raise ValueError('Nonfinite earnings')
    result={'period_end':str(period),'revenue_usd':str(_positive(d['revenue_usd'])),
            'net_income_usd':str(net), 'revenue_filed_date':str(revfiled),
            'earnings_filed_date':str(incfiled),'status':d.get('status','SYNTHETIC_NOT_REPORTED')}
    if 'source_filing_accession' in d:
        accession=d['source_filing_accession']
        if accession is not None and (not isinstance(accession,str) or len(accession)>40):
            raise ValueError('Invalid SEC accession')
        result['source_filing_accession']=accession
    return result


def _get_source_bytes(meta:dict):
    raw_path=Path(meta['path']).expanduser()
    payload=raw_path.read_bytes()
    if not payload or len(payload)>MAX_BYTES: raise ValueError('Empty or oversized input')
    provider=meta['provider']
    is_synthetic=provider.startswith('SYNTHETIC_')
    claimed_hash=meta.get('sha256')
    if not is_synthetic and (not isinstance(claimed_hash,str) or
                             not re.fullmatch(r'[0-9a-f]{64}',claimed_hash)):
        raise ValueError('External source requires a complete declared SHA-256')
    if claimed_hash and sha256_bytes(payload)!=claimed_hash:
        raise ValueError('Source hash differs from declared snapshot; fail closed')
    source_url=str(meta.get('source_url',''))
    if meta['provider']=='SEC_COMPANYFACTS' and not source_url.startswith(SEC_HOST):
        raise ValueError('SEC data must originate from an official companyfacts URL')
    if meta['provider']=='ECB_EUR_FX' and source_url not in (ECB_URL,ECB_CSV_URL):
        raise ValueError('ECB FX must originate from the approved source endpoint')
    if meta['provider']==YFINANCE:
        if not re.fullmatch(r'https://finance\.yahoo\.com/quote/[A-Za-z0-9%._^=\-]{1,100}/history/',source_url):
            raise ValueError('Unverified price feed does not match Yahoo Finance disclosure URL')
    if meta['provider']==MANUAL_OHLCV:
        # Attestation is never a claim that the software independently checked
        # the provider license. No automatic download or public redistribution.
        if meta.get('usage_attestation')!='LOCAL_RESEARCH_RIGHTS_ASSERTED_NOT_VERIFIED':
            raise ValueError('Manual price input requires explicit local-use rights attestation')
        if not meta.get('retrieved_at_utc'):
            raise ValueError('Manual price input requires collection provenance timestamp')
        parsed=urlsplit(source_url)
        if (parsed.scheme!='https' or not parsed.hostname or parsed.username or
                parsed.password or parsed.fragment or parsed.hostname.lower() in ('localhost','127.0.0.1')):
            raise ValueError('Manual OHLCV requires a declared HTTPS provider URL')
    if not source_url.startswith('https://') and not is_synthetic:
        raise ValueError('External source requires HTTPS provenance URL')
    return payload



def _validate_manual_price_evidence(source:dict, as_of:date, bars:list[dict]):
    """Fail closed when a claimed local snapshot could not yet contain its bars.

    Attested source rights are still NOT authenticated; this is a structural
    point-in-time and metadata check only, not a market data certification.
    """
    raw=source.get('retrieved_at_utc')
    if not isinstance(raw,str):
        raise ValueError('Manual price retrieval timestamp must be timezone-aware UTC ISO 8601')
    try:
        retrieved=datetime.fromisoformat(raw.replace('Z','+00:00'))
    except ValueError:
        raise ValueError('Manual price retrieval timestamp must be timezone-aware UTC ISO 8601') from None
    if retrieved.tzinfo is None or retrieved.utcoffset()!=timedelta(0):
        raise ValueError('Manual price retrieval timestamp requires an explicit UTC offset')
    if retrieved.date()>as_of:
        raise ValueError('Manual price snapshot collected after as_of date')
    if retrieved.date()<date.fromisoformat(bars[-1]['date']):
        raise ValueError('Manual price snapshot predates its latest price session')
    split_dates=source.get('split_dates',[])
    if not isinstance(split_dates,list):
        raise ValueError('Declared split_dates must be a list of ISO dates')
    seen=set()
    for raw_split in split_dates:
        if not isinstance(raw_split,str):
            raise ValueError('Declared split_dates must contain ISO dates')
        try:
            split=date.fromisoformat(raw_split)
        except ValueError:
            raise ValueError('Declared split_dates must contain ISO dates') from None
        if split>as_of:
            raise ValueError('Declared split date is after the research as_of')
        if split in seen:
            raise ValueError('Duplicate declared split date')
        seen.add(split)

def _write_checked(base:Path, relpath:str, payload:bytes):
    target=base / relpath
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(payload)
    return {'path':relpath,'sha256':sha256_bytes(payload),'bytes':len(payload)}


def _csv_bytes(rows, fields):
    handle=io.StringIO(newline='')
    writer=csv.DictWriter(handle,fieldnames=fields,lineterminator='\n')
    writer.writeheader();writer.writerows([{k:r[k] for k in fields} for r in rows])
    return handle.getvalue().encode('utf-8')



def parse_events(payload:bytes, as_of:date, *, synthetic:bool):
    """Auditable event register; no event is interpreted as a prediction."""
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    expected=['event_id','asset_id','event_date','published_date','category','description','source_url']
    if reader.fieldnames!=expected:
        raise ValueError('Event register requires '+','.join(expected))
    result=[];seen=set()
    for r in reader:
        if None in r or any(v is None for v in r.values()):
            raise ValueError('Malformed event row')
        if not r['event_id'] or r['event_id'] in seen: raise ValueError('Duplicate/blank event_id')
        seen.add(r['event_id'])
        event_date=date.fromisoformat(r['event_date'])
        published=date.fromisoformat(r['published_date'])
        if published>as_of: continue  # no future news / lookahead
        if not r['description'].strip() or r['category'] not in ('earnings','macro','policy','geopolitics','other'):
            raise ValueError('Invalid event context')
        if not synthetic and not r['source_url'].startswith('https://'):
            raise ValueError('External event requires source URL')
        result.append(r)
    return sorted(result,key=lambda x:(x['event_date'],x['event_id']))


def build_bundle(spec:dict, output:Path):
    """Normalize imported local files. No network and no unstated fallbacks."""
    as_of=date.fromisoformat(spec['as_of'])
    mode=spec['mode']
    if mode not in (SYNTHETIC, EXTERNAL): raise ValueError('Unknown dataset mode')
    output=Path(output)
    if mode==EXTERNAL and any(a.get('prices_source',{}).get('provider') in
                             ('EODHD_EOD_PERSONAL_RESEARCH','TIINGO_EOD_PERSONAL_RESEARCH',
                              FWB_PERSONAL_HISTORY)
                             for a in spec['assets']):
        base=Path(__file__).resolve().parents[2]
        location=output.resolve()
        if location.is_relative_to(base) and not location.is_relative_to(base/'data/private'):
            raise ValueError('External licensed research bundle inside repo must be in data/private')
    output.mkdir(parents=True,exist_ok=True)
    assets=[]; seen=set(); source_kinds=set()
    for row in spec['assets']:
        uid=row['id']
        if not uid or not uid.replace('_','').replace('-','').isalnum() or uid in seen:
            raise ValueError('Invalid/duplicate research ID')
        seen.add(uid)
        ccy=row['currency'];venue=row['venue']
        if ccy not in ('EUR','USD') or not venue:
            raise ValueError('Only EUR/USD with explicit venue currently supported')
        source=row['prices_source']
        if mode==EXTERNAL and source['provider'].startswith('SYNTHETIC'):
            raise ValueError('Synthetic prices cannot be promoted to external research')
        payload=_get_source_bytes(source)
        eodhd_meta=None
        tiingo_meta=None
        fwb_meta=None
        if source['provider'] in (YFINANCE, MANUAL_OHLCV):
            records=parse_ohlcv(payload,as_of)
        elif source['provider']=='EODHD_EOD_PERSONAL_RESEARCH' and mode==EXTERNAL:
            from .research_eodhd_local import normalize_private_eodhd
            records,eodhd_meta=normalize_private_eodhd(
                source,payload,as_of,row,repo_root=Path(__file__).resolve().parents[2])
        elif source['provider']=='TIINGO_EOD_PERSONAL_RESEARCH' and mode==EXTERNAL:
            from .research_tiingo_local import normalize_private_tiingo
            records,tiingo_meta=normalize_private_tiingo(
                source,payload,as_of,row,repo_root=Path(__file__).resolve().parents[2])
        elif source['provider']==FWB_PERSONAL_HISTORY and mode==EXTERNAL:
            from .research_fwb_local import normalize_private_fwb
            records,fwb_meta=normalize_private_fwb(
                source,payload,as_of,row,repo_root=Path(__file__).resolve().parents[2])
        elif source['provider']=='SYNTHETIC_PRICES' and mode==SYNTHETIC:
            records=parse_normalized_prices(payload,as_of)
        else: raise ValueError('Unsupported price source; do not infer provider format')
        if mode==EXTERNAL and source['provider'].startswith('SYNTHETIC'):
            raise ValueError('Synthetic prices cannot be promoted to external research')
        if source['provider']==MANUAL_OHLCV:
            _validate_manual_price_evidence(source,as_of,records)
        source_kinds.add(source['provider'])
        entry={k:row.get(k,'') for k in ('id','name','isin','asset_type','sector','venue','currency','oil_exposure','index_memberships','index_membership_status')}
        if entry.get('isin') and not valid_isin(entry['isin']):
            raise ValueError(f"Invalid ISIN: {uid}")
        source_note={'provider':source['provider'],'source_url':source.get('source_url',''),
                     'retrieved_at_utc':source.get('retrieved_at_utc'),
                     'raw_sha256':sha256_bytes(payload),
                     'price_basis':('MANUAL_CLOSE_UNADJUSTED_NOT_TOTAL_RETURN' if source['provider']==MANUAL_OHLCV
                                    else source.get('price_basis','UNVERIFIED_UNADJUSTED_CLOSE')),
                     'split_dates':source.get('split_dates',[]),
                     'data_warning':'Not an executable bid/ask quote or total-return price'}
        if source['provider']==MANUAL_OHLCV:
            source_note['usage_rights_status']='USER_ASSERTED_LOCAL_ONLY_NEVER_VERIFIED_BY_ENGINE'
        if eodhd_meta is not None:
            source_note.update(eodhd_meta)
            source_kinds.update(('EODHD_PERSONAL_SPLITS','EODHD_PERSONAL_DIVIDENDS'))
        if tiingo_meta is not None:
            source_note.update(tiingo_meta)
        if fwb_meta is not None:
            source_note.update(fwb_meta)
        entry['prices']={**_write_checked(output,f'prices/{uid}.csv',_csv_bytes(records,['date','close','volume'])),**source_note}
        fmeta=row.get('fundamentals_source')
        if fmeta:
            raw=_get_source_bytes(fmeta)
            if fmeta['provider']=='SEC_COMPANYFACTS':
                cik=str(row.get('sec_cik',''))
                source_suffix=f'CIK{cik.zfill(10)}.json'
                if not cik.isdigit() or len(cik)>10 or not fmeta.get('source_url','').endswith(source_suffix):
                    raise ValueError('SEC CIK must match the official companyfacts URL and instrument')
                if str(json.loads(raw).get('cik'))!=str(int(cik)):
                    raise ValueError('SEC companyfacts CIK does not match the instrument')
                f=parse_sec_fundamentals(raw,as_of)
            elif fmeta['provider']=='SYNTHETIC_FUNDAMENTALS' and mode==SYNTHETIC:
                f=parse_synthetic_fundamentals(raw,as_of)
            else: raise ValueError('Unsupported fundamentals provider')
            if mode==EXTERNAL and fmeta['provider'].startswith('SYNTHETIC'):
                raise ValueError('Synthetic fundamentals cannot be promoted to external research')
            source_kinds.add(fmeta['provider'])
            fbytes=(json.dumps(f,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
            entry['fundamentals']={**_write_checked(output,f'fundamentals/{uid}.json',fbytes),
                'provider':fmeta['provider'],'source_url':fmeta.get('source_url',''),
                'retrieved_at_utc':fmeta.get('retrieved_at_utc'), 'raw_sha256':sha256_bytes(raw)}
        assets.append(entry)
    fxmeta=spec.get('fx_source');fxinfo=None
    if any(a['currency']=='USD' for a in assets) and fxmeta is None:
        # Missing FX is not silently substituted: ranking will remain incomplete.
        pass
    if fxmeta:
        raw=_get_source_bytes(fxmeta)
        if mode==EXTERNAL and fxmeta['provider'].startswith('SYNTHETIC'):
            raise ValueError('Synthetic FX cannot be promoted to external research')
        if fxmeta['provider']=='ECB_EUR_FX': data=parse_ecb(raw,as_of)
        elif fxmeta['provider']=='SYNTHETIC_FX' and mode==SYNTHETIC:
            data=parse_normalized_fx(raw,as_of)
        else: raise ValueError('Unsupported FX source')
        source_kinds.add(fxmeta['provider'])
        fxinfo={**_write_checked(output,'fx/eur_usd.csv',_csv_bytes(data,['date','usd_per_eur'])),
            'provider':fxmeta['provider'],'source_url':fxmeta.get('source_url',''),
            'retrieved_at_utc':fxmeta.get('retrieved_at_utc'),'raw_sha256':sha256_bytes(raw),'unit':'USD per EUR'}
    event_source=spec.get('events_source');events_info=None
    if event_source:
        if mode==EXTERNAL and event_source.get('provider')!='MANUAL_DOCUMENTED_EVENTS':
            raise ValueError('External events must have documented sources')
        if mode==SYNTHETIC and event_source.get('provider')!='SYNTHETIC_EVENTS':
            raise ValueError('Demo events must be labelled synthetic')
        raw=_get_source_bytes(event_source)
        events=parse_events(raw,as_of,synthetic=mode==SYNTHETIC)
        valid_ids={a['id'] for a in assets}
        if any(e['asset_id']!='*' and e['asset_id'] not in valid_ids for e in events):
            raise ValueError('Event references missing instrument')
        source_kinds.add(event_source['provider'])
        events_info={**_write_checked(output,'events/register.csv',_csv_bytes(events,[
            'event_id','asset_id','event_date','published_date','category','description','source_url'])),
            'provider':event_source['provider'],'raw_sha256':sha256_bytes(raw)}
    manifest={'schema_version':1,'mode':mode,'as_of':as_of.isoformat(),
              'assets':assets,'fx':fxinfo,'events':events_info,'source_kinds':sorted(source_kinds),
              'disclaimer':'Only as-of dated, hash-matched research inputs. No live quotes, orders or performance forecasts.'}
    manifest_path=output/'manifest.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


def _read_checked_file(bundle:Path, filemeta:dict):
    rel=Path(filemeta['path'])
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe path in dataset manifest')
    path=(bundle/rel).resolve()
    if not path.is_relative_to(bundle.resolve()): raise ValueError('Dataset symlink escapes bundle')
    data=path.read_bytes()
    if not data or len(data)>MAX_BYTES or sha256_bytes(data)!=filemeta['sha256']:
        raise ValueError(f'Dataset hash mismatch or invalid file: {rel}')
    return data


def load_bundle(path:Path):
    path=Path(path)
    manifest_path=path/'manifest.json'
    m=json.loads(manifest_path.read_text(encoding='utf-8'))
    if m.get('schema_version')!=1 or m.get('mode') not in (SYNTHETIC,EXTERNAL):
        raise ValueError('Unsupported research bundle')
    as_of=date.fromisoformat(m['as_of'])
    seen=set();items=[]
    for row in m['assets']:
        uid=row['id']
        if uid in seen: raise ValueError('Duplicate research bundle instrument')
        seen.add(uid)
        bars=parse_normalized_prices(_read_checked_file(path,row['prices']),as_of)
        facts=None
        if row.get('fundamentals'):
            raw=_read_checked_file(path,row['fundamentals'])
            facts=parse_synthetic_fundamentals(raw,as_of)  # schema validation, regardless of origin
        items.append((row,bars,facts))
    fx=None
    if m.get('fx'):
        fx=parse_normalized_fx(_read_checked_file(path,m['fx']),as_of)
    events=[]
    if m.get('events'):
        events=parse_events(_read_checked_file(path,m['events']),as_of,synthetic=m['mode']==SYNTHETIC)
    return m,items,fx,events
