"""Explicit, offline-by-default free data collection with immutable evidence.

No arbitrary URL fetching, automatic retries, paid APIs, or redistribution of
provider payloads. Use the SEC's official EDGAR XBRL API and ECB reference FX;
Stooq history is opt-in and unverified, with provider terms to be reviewed.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_BYTES = 20_000_000
SEC_HOST = 'https://data.sec.gov/api/xbrl/companyfacts/'
ECB_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv'
STOOQ_URL = 'https://stooq.com/q/d/l/'


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Provider redirected; new endpoint requires explicit review')


def source_request(provider: str, identifier: str = '', *, sec_contact: str = '',
                   stooq_key: str = '', acknowledge_stooq_terms: bool = False):
    """Return a fixed-host Request and a key-redacted source descriptor."""
    if provider == 'SEC_COMPANYFACTS':
        if not re.fullmatch(r'\d{1,10}', identifier):
            raise ValueError('SEC identifier must be a CIK containing 1-10 digits')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', sec_contact):
            raise ValueError('SEC requires a real, explicitly supplied contact email')
        identifier = identifier.zfill(10)
        url = SEC_HOST + f'CIK{identifier}.json'
        headers = {'User-Agent': f'InvestmentResearchDev/0.2 research {sec_contact}', 'Accept': 'application/json'}
        return Request(url, headers=headers), url
    if provider == 'ECB_EUR_FX':
        if identifier:
            raise ValueError('ECB FX needs no identifier')
        return Request(ECB_URL, headers={'User-Agent': 'InvestmentResearchDev/0.2'}), ECB_URL
    if provider == 'STOOQ_EOD_UNVERIFIED':
        if not acknowledge_stooq_terms or not stooq_key:
            raise ValueError('Stooq requires explicit terms acknowledgement and a free API key')
        if not re.fullmatch(r'[a-z0-9^._-]{1,36}', identifier.lower()):
            raise ValueError('Invalid Stooq symbol')
        params = urlencode({'s': identifier.lower(), 'i': 'd', 'apikey': stooq_key})
        return Request(STOOQ_URL + '?' + params, headers={'User-Agent': 'InvestmentResearchDev/0.2'}), STOOQ_URL + '?s=' + identifier.lower() + '&i=d&apikey=REDACTED'
    raise ValueError('Unsupported provider; no automatic provider fallback')


def collect(provider: str, identifier: str, cache: Path, *, sec_contact='',
            stooq_key='', acknowledge_stooq_terms=False, transport=None):
    """One explicit network request; cache immutable bytes + redacted metadata."""
    request, descriptor = source_request(provider, identifier, sec_contact=sec_contact,
        stooq_key=stooq_key, acknowledge_stooq_terms=acknowledge_stooq_terms)
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
    elif provider == 'ECB_EUR_FX':
        if 'Date' not in payload[:500].decode('utf-8-sig'):
            raise ValueError('Invalid ECB FX CSV header')
    else:
        if b'Date,Open,High,Low,Close,Volume' not in payload[:300] or b'\x3chtml' in payload[:500].lower():
            raise ValueError('Stooq returned a denial or non-price response; do not treat it as data')
    digest = sha256_bytes(payload)
    dest = Path(cache) / provider / (identifier or 'EUR_FX')
    dest.mkdir(parents=True, exist_ok=True)
    raw_path = dest / (digest + '.bin')
    if raw_path.exists() and sha256_bytes(raw_path.read_bytes()) != digest:
        raise ValueError('Cache collision or corruption')
    if not raw_path.exists():
        raw_path.write_bytes(payload)
    meta = {'provider': provider, 'identifier': identifier, 'source_url': descriptor,
        'sha256': digest, 'bytes': len(payload),
        'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'path': str(raw_path), 'status': 'UNVERIFIED_PROVIDER_PAYLOAD',
        'license': 'Review provider terms before using or redistributing market data'}
    (dest / (digest + '.json')).write_text(json.dumps(meta, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    return meta


def parse_stooq(data: bytes, as_of: date):
    """Validate Stooq OHLCV; outputs normalized close, not known adjusted prices."""
    text = data.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ['Date','Open','High','Low','Close','Volume']:
        raise ValueError('Invalid Stooq OHLCV schema')
    rows, dates = [], set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Malformed Stooq row')
        d = date.fromisoformat(row['Date'])
        if d > as_of or d in dates:
            if d > as_of: continue  # point-in-time cutoff
            raise ValueError('Duplicate Stooq price session')
        dates.add(d)
        try:
            nums = {k: Decimal(row[k]) for k in ['Open','High','Low','Close','Volume']}
        except InvalidOperation as exc:
            raise ValueError('Non-numeric Stooq price') from exc
        if any(not v.is_finite() for v in nums.values()) or any(nums[x] <= 0 for x in ['Open','High','Low','Close']) or nums['Volume'] < 0:
            raise ValueError('Invalid Stooq price/volume')
        if nums['Low'] > min(nums['Open'],nums['Close']) or nums['High'] < max(nums['Open'],nums['Close']) or nums['High'] < nums['Low']:
            raise ValueError('Inconsistent Stooq OHLC')
        rows.append({'date':str(d), 'close': str(nums['Close']), 'volume':str(nums['Volume'])})
    if not rows:
        raise ValueError('No historical prices at or before as_of')
    return sorted(rows, key=lambda x:x['date'])


def parse_ecb(data: bytes, as_of: date):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    if reader.fieldnames:
        reader.fieldnames = [col.strip() for col in reader.fieldnames]
    if not reader.fieldnames or 'Date' not in reader.fieldnames or 'USD' not in reader.fieldnames:
        raise ValueError('ECB CSV must contain Date and USD')
    result = {}
    for r in reader:
        d = date.fromisoformat(r['Date'].strip())
        if d > as_of: continue
        if d.isoformat() in result:
            raise ValueError('Duplicate ECB FX date')
        try: rate = Decimal(r['USD'].strip())
        except InvalidOperation as exc: raise ValueError('Invalid ECB USD FX') from exc
        if not rate.is_finite() or rate <= 0:
            raise ValueError('Invalid ECB FX value')
        result[d.isoformat()] = {'date':d.isoformat(), 'usd_per_eur':str(rate)}
    if not result: raise ValueError('No ECB rates before as_of')
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
                out.append((end,filed,-precedence,tag,str(value)))
        return out
    rev = candidates(concepts['revenue']); inc = candidates(concepts['net_income'])
    same_end = {r[0] for r in rev} & {r[0] for r in inc}
    if not same_end: raise ValueError('No same-period SEC annual revenue and earnings available as_of')
    period = max(same_end)
    r = max((x for x in rev if x[0] == period), key=lambda x:(x[1],x[2]))
    n = max((x for x in inc if x[0] == period), key=lambda x:(x[1],x[2]))
    return {'period_end': period.isoformat(), 'revenue_usd':r[4], 'net_income_usd':n[4],
            'revenue_filed_date':r[1].isoformat(), 'earnings_filed_date':n[1].isoformat(),
            'revenue_concept':r[3], 'earnings_concept':n[3], 'status':'SEC_ANNUAL_FILED_BY_AS_OF'}
