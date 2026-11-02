"""Explicit, offline-by-default free data collection with immutable evidence.

No arbitrary URL fetching, automatic retries, paid APIs, or redistribution of
provider payloads. Use the SEC's official EDGAR XBRL API and ECB reference FX;
Yahoo/yfinance is an optional, unverified personal-research adapter; no data redistribution.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_BYTES = 20_000_000
SEC_HOST = 'https://data.sec.gov/api/xbrl/companyfacts/'
SEC_TICKERS_URL = 'https://www.sec.gov/files/company_tickers_exchange.json'
ECB_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'
ECB_CSV_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv'
YAHOO_HISTORY_URL = 'https://finance.yahoo.com/quote/'
YFINANCE = 'YFINANCE_EOD_UNVERIFIED'


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Provider redirected; new endpoint requires explicit review')


def source_request(provider: str, identifier: str = '', *, sec_contact: str = ''):
    """Return allowlisted official HTTP request; yfinance is a separate adapter."""
    if provider == 'SEC_COMPANYFACTS':
        if not re.fullmatch(r'\d{1,10}', identifier):
            raise ValueError('SEC identifier must be a CIK containing 1-10 digits')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', sec_contact):
            raise ValueError('SEC requires a real, explicitly supplied contact email')
        identifier = identifier.zfill(10)
        url = SEC_HOST + f'CIK{identifier}.json'
        headers = {'User-Agent': f'InvestmentResearchDev/0.2 research {sec_contact}', 'Accept': 'application/json'}
        return Request(url, headers=headers), url
    if provider == 'SEC_TICKERS':
        if identifier:
            raise ValueError('SEC ticker catalog needs no identifier')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', sec_contact):
            raise ValueError('SEC requires a real, explicitly supplied contact email')
        return Request(SEC_TICKERS_URL, headers={'User-Agent': f'InvestmentResearchDev/0.3 research {sec_contact}', 'Accept': 'application/json'}), SEC_TICKERS_URL
    if provider == 'ECB_EUR_FX':
        if identifier:
            raise ValueError('ECB FX needs no identifier')
        return Request(ECB_URL, headers={'User-Agent': 'InvestmentResearchDev/0.3', 'Accept':'application/xml'}), ECB_URL
    raise ValueError('Unsupported provider; no automatic provider fallback')


def collect(provider: str, identifier: str, cache: Path, *, sec_contact='',
            acknowledge_yahoo_terms=False, as_of=None, transport=None,
            history_loader=None):
    """Explicit provider request; caching never claims trade-ready prices."""
    if provider == YFINANCE:
        return collect_yfinance(identifier, cache, acknowledge_terms=acknowledge_yahoo_terms,
                                as_of=as_of, history_loader=history_loader)
    request, descriptor = source_request(provider, identifier, sec_contact=sec_contact)
    if transport is None:
        transport = build_opener(_NoRedirect()).open
    try:
        with transport(request, timeout=20) as response:
            payload = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        if exc.code in (403, 429):
            raise RuntimeError(f'{provider}: access or rate limit ({exc.code}); no retries or paid fallback') from exc
        raise RuntimeError(f'{provider}: HTTP {exc.code}') from exc
    except URLError as exc:
        raise RuntimeError(f'{provider}: network unavailable ({exc.reason})') from exc
    if len(payload) > MAX_BYTES or not payload.strip():
        raise ValueError('Provider response is oversized or empty')
    if provider == 'SEC_COMPANYFACTS':
        obj = json.loads(payload)
        if not isinstance(obj.get('facts'), dict):
            raise ValueError('Invalid SEC companyfacts JSON')
        if str(obj.get('cik')) != str(int(identifier)):
            raise ValueError('SEC CIK in payload does not match requested company')
    elif provider == 'SEC_TICKERS':
        from .research_universe import parse_sec_tickers
        parse_sec_tickers(payload)
    elif provider == 'ECB_EUR_FX':
        parsed=parse_ecb(payload, date.today())
        if date.fromisoformat(parsed[-1]['date']) < date.today()-timedelta(days=14):
            raise ValueError('ECB FX provider response is stale; reject even if parseable')
    return _save_snapshot(provider, identifier, cache, descriptor, payload)


def _valid_yahoo_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Za-z0-9^._=\-]{1,36}', symbol):
        raise ValueError('Invalid Yahoo symbol: only known market symbol characters allowed')
    return symbol.upper()


def yahoo_source_url(symbol: str) -> str:
    """Disclosure URL only: yfinance is a third-party library, not direct HTTP to this URL."""
    return YAHOO_HISTORY_URL + quote(_valid_yahoo_symbol(symbol), safe='._-') + '/history/'


def _serialize_yahoo_history(frame, as_of: date) -> tuple[bytes, dict]:
    """Convert library OHLCV to strict, reviewable canonical CSV.

    Never use Adj Close as executable price; dividends are NOT added to returns.
    Provider Close can contain split revisions; we block known splits pending review.
    """
    required=('Open','High','Low','Close','Volume')
    if frame is None or getattr(frame,'empty', True):
        raise ValueError('yfinance returned empty historical prices; not a valid snapshot')
    if any(field not in frame.columns for field in required):
        raise ValueError('yfinance returned missing OHLCV fields')
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['Date','Open','High','Low','Close','Volume'])
    split_dates=[];dividend_dates=[];count=0
    for ix, row in frame.iterrows():
        day=ix.date() if hasattr(ix,'date') else date.fromisoformat(str(ix)[:10])
        if day>as_of:continue
        cells=[str(row[field]) for field in required]
        writer.writerow([day.isoformat(),*cells])
        count+=1
        for field, record in (('Stock Splits',split_dates),('Dividends',dividend_dates)):
            if field in frame.columns:
                try: val=Decimal(str(row[field]))
                except (InvalidOperation,TypeError,ValueError) as exc:
                    raise ValueError(f'Invalid yfinance {field}') from exc
                if not val.is_finite() or val<0:raise ValueError(f'Invalid yfinance {field}')
                if val>0:record.append(day.isoformat())
    payload=stream.getvalue().encode('utf-8')
    if not count:raise ValueError('No Yahoo trading days within as_of')
    parse_ohlcv(payload,as_of)  # fail closed before caching
    return payload,{'price_basis':'YAHOO_CLOSE_AUTO_ADJUST_FALSE_NOT_TOTAL_RETURN',
                    'split_dates':sorted(set(split_dates)),
                    'dividend_dates':sorted(set(dividend_dates)),
                    'library':'yfinance',
                    'source_claim':'THIRD_PARTY_UNVERIFIED_CANONICAL_EXPORT',
                    'license':'Personal research only per Yahoo/yfinance terms; never publish downloaded data'}


def collect_yfinance(symbol: str, cache: Path, *, acknowledge_terms=False, as_of=None,
                     history_loader=None):
    """Explicit opt-in only; no key, no automatic retries, no silent source fallback.

    history_loader is a test seam; production uses yfinance.Ticker.history.
    """
    if not acknowledge_terms:
        raise ValueError('Yahoo/yfinance requires explicit acknowledgement of personal-use terms')
    symbol=_valid_yahoo_symbol(symbol)
    cutoff = as_of or date.today()
    if isinstance(cutoff,str):cutoff=date.fromisoformat(cutoff)
    if not isinstance(cutoff,date) or cutoff>date.today():
        raise ValueError('Future or malformed as_of for Yahoo collection')
    start=cutoff-timedelta(days=440); end=cutoff+timedelta(days=1)
    if history_loader is None:
        try: import yfinance as yf
        except ImportError as exc:
            raise RuntimeError('yfinance is optional: install with pip install -e .[data]') from exc
        def history_loader(sym, left, right):
            return yf.Ticker(sym).history(start=left.isoformat(),end=right.isoformat(),
                interval='1d',auto_adjust=False,actions=True,repair=False,
                keepna=True,raise_errors=True,timeout=20)
    try:
        frame=history_loader(symbol,start,end)
    except Exception as exc:
        # Do not print request headers, cookies or possible tokens in exception text.
        raise RuntimeError('Yahoo/yfinance historical retrieval failed; no fallback or retry') from None
    payload,extra=_serialize_yahoo_history(frame,cutoff)
    return _save_snapshot(YFINANCE,symbol,cache,yahoo_source_url(symbol),payload,extra)


def _save_snapshot(provider, identifier, cache, descriptor, payload, extra=None):
    """Immutable content-addressed local cache, shared by official and unofficial sources."""
    if len(payload)>MAX_BYTES or not payload.strip():raise ValueError('Empty or oversized source payload')
    digest=sha256_bytes(payload)
    dest=Path(cache)/provider/(identifier or ('SEC_CATALOG' if provider=='SEC_TICKERS' else 'EUR_FX'))
    dest.mkdir(parents=True,exist_ok=True)
    raw_path=dest/(digest+'.bin')
    if raw_path.exists() and sha256_bytes(raw_path.read_bytes())!=digest:
        raise ValueError('Cache collision or corruption')
    if not raw_path.exists():raw_path.write_bytes(payload)
    meta={'provider':provider,'identifier':identifier,'source_url':descriptor,'sha256':digest,
          'bytes':len(payload),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
          'path':str(raw_path),'status':'UNVERIFIED_PROVIDER_PAYLOAD',
          'license':'Check provider rights before further use or redistribution'}
    if extra: meta.update(extra)
    (dest/(digest+'.json')).write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return meta

def parse_ohlcv(data: bytes, as_of: date):
    """Validate canonical OHLCV CSV; Yahoo Close without dividend total-return adjustment, NOT a total return."""
    text = data.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ['Date','Open','High','Low','Close','Volume']:
        raise ValueError('Invalid OHLCV schema')
    rows, dates = [], set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Malformed OHLCV row')
        d = date.fromisoformat(row['Date'])
        if d > as_of or d in dates:
            if d > as_of: continue  # point-in-time cutoff
            raise ValueError('Duplicate OHLCV price session')
        dates.add(d)
        try:
            nums = {k: Decimal(row[k]) for k in ['Open','High','Low','Close','Volume']}
        except InvalidOperation as exc:
            raise ValueError('Non-numeric OHLCV price') from exc
        if any(not v.is_finite() for v in nums.values()) or any(nums[x] <= 0 for x in ['Open','High','Low','Close']) or nums['Volume'] < 0:
            raise ValueError('Invalid OHLCV price/volume')
        if nums['Low'] > min(nums['Open'],nums['Close']) or nums['High'] < max(nums['Open'],nums['Close']) or nums['High'] < nums['Low']:
            raise ValueError('Inconsistent OHLC')
        rows.append({'date':str(d), 'close': str(nums['Close']), 'volume':str(nums['Volume'])})
    if not rows:
        raise ValueError('No historical prices at or before as_of')
    return sorted(rows, key=lambda x:x['date'])


def parse_ecb(data: bytes, as_of: date):
    """Read official BCE XML (current default) or legacy CSV, fail closed on age.

    Date sorting is explicit. This parser validates values; live collector separately
    verifies recency so a stale but well-formed historical snapshot is rejected.
    """
    result={}
    if data.lstrip().startswith(b'<'):
        try: root=ET.fromstring(data)
        except ET.ParseError as exc:raise ValueError('Invalid ECB XML') from exc
        for el in root.iter():
            if el.tag.split('}')[-1]!='Cube' or 'time' not in el.attrib:
                continue
            d=date.fromisoformat(el.attrib['time'])
            if d.weekday()>=5:raise ValueError('ECB fixing dated on weekend')
            if d>as_of:continue
            usd=[child.attrib['rate'] for child in el
                 if child.tag.split('}')[-1]=='Cube' and child.attrib.get('currency')=='USD']
            if len(usd)!=1:continue
            if d.isoformat() in result:raise ValueError('Duplicate ECB XML date')
            try:rate=Decimal(usd[0])
            except InvalidOperation as exc:raise ValueError('Invalid ECB USD FX') from exc
            if not rate.is_finite() or rate<=0:raise ValueError('Invalid ECB FX value')
            result[d.isoformat()]={'date':d.isoformat(),'usd_per_eur':str(rate)}
    else:
        reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
        if reader.fieldnames:
            reader.fieldnames=[col.strip() for col in reader.fieldnames]
        if not reader.fieldnames or 'Date' not in reader.fieldnames or 'USD' not in reader.fieldnames:
            raise ValueError('ECB CSV must contain Date and USD')
        for r in reader:
            d=date.fromisoformat(r['Date'].strip())
            if d.weekday()>=5:raise ValueError('ECB fixing dated on weekend')
            if d>as_of:continue
            if d.isoformat() in result:raise ValueError('Duplicate ECB FX date')
            try:rate=Decimal(r['USD'].strip())
            except InvalidOperation as exc:raise ValueError('Invalid ECB USD FX') from exc
            if not rate.is_finite() or rate<=0:raise ValueError('Invalid ECB FX value')
            result[d.isoformat()]={'date':d.isoformat(),'usd_per_eur':str(rate)}
    if not result:raise ValueError('No ECB rates before as_of')
    return [result[x] for x in sorted(result)]


def _sec_facts(data: bytes, as_of: date):
    body = json.loads(data)
    if not isinstance(body.get('facts',{}).get('us-gaap'),dict):
        raise ValueError('Missing SEC us-gaap XBRL facts')
    return body['facts']['us-gaap']


def parse_sec_fundamentals(data: bytes, as_of: date):
    """Choose annual revenue and earnings from the *same* fiscal year.

    Only USD, 10-K full-year duration items, and filed dates <= as_of.
    Corrections filed after as_of are excluded (point-in-time rule).
    """
    facts = _sec_facts(data, as_of)
    concepts = {
        'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'],
        'net_income': ['NetIncomeLoss'],
    }
    def candidates(tags):
        out=[]
        for precedence, tag in enumerate(tags):
            for r in facts.get(tag, {}).get('units', {}).get('USD', []):
                if r.get('form') not in ('10-K','10-K/A') or r.get('fp') != 'FY': continue
                try:
                    filed = date.fromisoformat(r['filed']); end = date.fromisoformat(r['end']); start = date.fromisoformat(r['start'])
                    value = Decimal(str(r['val']))
                except (KeyError, TypeError, ValueError, InvalidOperation): continue
                if filed > as_of or end > filed or not 300 <= (end-start).days <= 390: continue
                if not value.is_finite(): continue
                out.append((end,filed,-precedence,tag,str(value),r.get('accn')))
        return out
    rev = candidates(concepts['revenue']); inc = candidates(concepts['net_income'])
    same_end = {r[0] for r in rev} & {r[0] for r in inc}
    if not same_end: raise ValueError('No same-period SEC annual revenue and earnings available as_of')
    period = max(same_end)
    rev_period=[x for x in rev if x[0]==period]
    inc_period=[x for x in inc if x[0]==period]
    # Actual SEC companyfacts include accession IDs. Refuse mixed-period or
    # mixed-filing statements; revenues and earnings must refer to one filing.
    if any(x[5] for x in rev_period+inc_period):
        shared={x[5] for x in rev_period if x[5]} & {x[5] for x in inc_period if x[5]}
        if not shared: raise ValueError('No same-filing SEC annual revenue and earnings')
        pairs=[]
        for accn in shared:
            rv=max((x for x in rev_period if x[5]==accn),key=lambda x:(x[1],x[2]))
            iv=max((x for x in inc_period if x[5]==accn),key=lambda x:(x[1],x[2]))
            pairs.append((max(rv[1],iv[1]),rv,iv,accn))
        _,r,n,accession=max(pairs,key=lambda x:(x[0],x[3]))
    else:
        r=max(rev_period,key=lambda x:(x[1],x[2]))
        n=max(inc_period,key=lambda x:(x[1],x[2]))
        accession=None
    return {'period_end': period.isoformat(), 'revenue_usd':r[4], 'net_income_usd':n[4],
            'source_filing_accession':accession,
            'revenue_filed_date':r[1].isoformat(), 'earnings_filed_date':n[1].isoformat(),
            'revenue_concept':r[3], 'earnings_concept':n[3], 'status':'SEC_ANNUAL_FILED_BY_AS_OF'}
