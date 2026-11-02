"""Quality, provenance, and stage-specific readiness, not trading authorization."""
from __future__ import annotations
import csv
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .market_calendar import VENUE_MAPPING, session_age
from .constraints import instrument_constraints

@dataclass(frozen=True)
class QualityStatus:
    gate: str
    severity: str
    message: str
    instrument_id: str = ''
    stage: str = 'RESEARCH'


def valid_isin(isin):
    isin = (isin or '').strip().upper()
    if len(isin) != 12 or not isin[:2].isalpha() or not isin[2:].isalnum():
        return False
    digits = ''.join(str(ord(c)-55) if c.isalpha() else c for c in isin)
    total = 0
    for i, digit in enumerate(reversed(digits)):
        n = int(digit) * (2 if i % 2 else 1)
        total += n // 10 + n % 10
    return total % 10 == 0


def read_strict_csv(path: Path, id_field='id'):
    with Path(path).open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or id_field not in reader.fieldnames:
            raise ValueError(f'Missing {id_field} in {path}')
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'Duplicate CSV header in {path}')
        rows, seen = [], set()
        for idx, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Malformed CSV line {idx} in {path}')
            key = row[id_field].strip()
            if not key or key in seen:
                raise ValueError(f'Blank/duplicate ID {key!r} in {path} line {idx}')
            seen.add(key)
            rows.append(row)
        return rows


def validate_instrument_mapping(instruments):
    """Same ISIN may appear on multiple venues/currencies, not in same listing twice."""
    listings, ids = {}, set()
    for row in instruments:
        uid = row['id'].strip()
        if not uid or uid in ids:
            raise ValueError(f'Duplicate/blank instrument ID: {uid}')
        ids.add(uid)
        isin = row.get('isin', '').strip().upper()
        ticker = row.get('ticker', '').strip().upper()
        venue = row.get('exchange', '').strip().upper()
        ccy = row.get('trade_currency', '').strip().upper()
        if not (ticker and venue and ccy):
            raise ValueError(f'Missing ticker/venue/currency mapping: {uid}')
        if isin and not valid_isin(isin):
            raise ValueError(f'Invalid nonblank ISIN: {uid}')
        # One ISIN on different venues is valid; same instrument listing duplicated is not.
        identity = (isin or 'UNIDENTIFIED:'+uid, venue, ccy)
        if identity in listings:
            raise ValueError(f'Ambiguous ISIN/venue/currency: {uid} and {listings[identity]}')
        listings[identity] = uid
    return True


def _item(gate, severity, msg, uid='', stage='RESEARCH'):
    return QualityStatus(gate, severity, msg, uid, stage)


def audit(instruments, quotes, reference_date: date, max_quote_age_sessions=1, settings=None):
    result = []
    known = {r['id'] for r in instruments}
    for row in instruments:
        uid = row['id']
        if not valid_isin(row.get('isin', '')):
            result.append(_item('isin', 'INCOMPLETE', f'{uid}: missing/invalid ISIN', uid, 'SHORTLIST'))
        for flag in instrument_constraints(row, settings or {}, new_purchase=True):
            result.append(_item(flag.code, flag.level, f'{uid}: {flag.message}', uid, 'SHORTLIST'))
        if row.get('fiscal_status') != 'eligible':
            result.append(_item('tax', 'INCOMPLETE', f'{uid}: ISIN-specific fiscal review', uid, 'PRETRADE'))
    for row in quotes:
        uid = row['id']
        if uid not in known:
            result.append(_item('mapping', 'BLOCKED', f'{uid}: unknown instrument', uid))
            continue
        try:
            price = Decimal(row['price'])
            day = date.fromisoformat(row['market_date'])
            if not price.is_finite() or price <= 0:
                raise ValueError('invalid price')
        except (ValueError, InvalidOperation, KeyError, TypeError):
            result.append(_item('quote', 'BLOCKED', f'{uid}: invalid quote', uid))
            continue
        if row.get('volume') is not None:
            try:
                volume = Decimal(row['volume'])
                if not volume.is_finite() or volume < 0:
                    raise ValueError('invalid volume')
            except (ValueError, InvalidOperation, TypeError):
                result.append(_item('volume', 'BLOCKED', f'{uid}: invalid quote volume', uid))
                continue
        if day > reference_date:
            result.append(_item('look_ahead', 'BLOCKED', f'{uid}: future quote', uid))
            continue
        instrument = next(x for x in instruments if x['id'] == uid)
        venue = VENUE_MAPPING.get(instrument.get('exchange'))
        if not venue:
            result.append(_item('calendar', 'INCOMPLETE', f'{uid}: calendar not supported', uid, 'SHORTLIST'))
        else:
            try:
                age = session_age(reference_date, day, venue)
                if age > max_quote_age_sessions:
                    result.append(_item('freshness', 'INCOMPLETE', f'{uid}: {age} sessions old', uid, 'SHORTLIST'))
            except ValueError as exc:
                result.append(_item('calendar', 'INCOMPLETE', f'{uid}: {exc}', uid, 'SHORTLIST'))
        if not row.get('source_url', '').startswith('https://'):
            result.append(_item('provenance', 'INCOMPLETE', f'{uid}: no HTTPS provenance URL', uid, 'SHORTLIST'))
    for uid in sorted(known - {q['id'] for q in quotes}):
        result.append(_item('coverage', 'INCOMPLETE', f'{uid}: missing quote', uid, 'SHORTLIST'))
    result.append(_item('live_order_book', 'INCOMPLETE', 'Executable bid/ask not available', stage='PRETRADE'))
    result.append(_item('tax_calendar', 'INCOMPLETE', 'Fiscal recognition date not confirmed', stage='PRETRADE'))
    return result


def readiness(statuses, uid):
    """Research may proceed with missing quotes; incomplete is not a buy signal."""
    relevant = [s for s in statuses if s.instrument_id in ('', uid)]
    stage_items = {
        'RESEARCH': [x for x in relevant if x.stage == 'RESEARCH'],
        'SHORTLIST': [x for x in relevant if x.stage in ('RESEARCH', 'SHORTLIST')],
        'PRETRADE': relevant,
    }
    result = {}
    for stage, items in stage_items.items():
        if any(x.severity == 'BLOCKED' for x in items):
            status = 'BLOCKED'
        elif any(x.severity == 'INCOMPLETE' for x in items):
            status = 'INCOMPLETE'
        elif any(x.severity == 'REVIEW' for x in items):
            status = 'ESTIMATED'
        else:
            status = 'VERIFIED'
        result[stage.lower() + '_readiness'] = status
    return result


def to_json(statuses):
    return [asdict(s) for s in statuses]
