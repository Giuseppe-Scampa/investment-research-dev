"""Trading and cash-settlement dates are distinct. 2026 known holidays are explicit.

No computed date is a broker-confirmed *tax recognition* date.
Markets outside 2026 are unsupported until calendar data is supplied.
"""
from datetime import date, timedelta

# Sources documented in docs/FISCAL_SOURCES.md. This is a deliberately scoped
# 2026 holiday set rather than an inferred universally correct calendar.
EXCHANGE_HOLIDAYS_2026 = {
    'XMIL': {'2026-01-01', '2026-04-03', '2026-04-06', '2026-05-01',
             '2026-12-24', '2026-12-25', '2026-12-31'},
    'XPAR': {'2026-01-01', '2026-04-03', '2026-04-06', '2026-05-01',
             '2026-12-25', '2026-12-26'},
    'XETR': {'2026-01-01', '2026-04-03', '2026-04-06', '2026-05-01',
             '2026-12-24', '2026-12-25', '2026-12-31'},
    'XNYS': {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03',
             '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07',
             '2026-11-26', '2026-12-25'},
    'XNAS': {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03',
             '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07',
             '2026-11-26', '2026-12-25'},
    # TARGET holidays: December 24 and 31 are NOT TARGET closures.
    'TARGET': {'2026-01-01', '2026-04-03', '2026-04-06', '2026-05-01',
               '2026-12-25', '2026-12-26'},
}

VENUE_MAPPING = {'Borsa Italiana': 'XMIL', 'Euronext Paris': 'XPAR',
                 'Xetra': 'XETR', 'NYSE': 'XNYS', 'Nasdaq': 'XNAS'}


def session(day: date, calendar: str) -> bool:
    if calendar not in EXCHANGE_HOLIDAYS_2026:
        raise ValueError(f'Unknown calendar: {calendar}')
    if day.year != 2026:
        raise ValueError('Validated 2026 calendars only; do not silently extrapolate')
    return day.weekday() < 5 and day.isoformat() not in EXCHANGE_HOLIDAYS_2026[calendar]


def last_session(day: date, calendar: str) -> date:
    if day.year != 2026:
        raise ValueError('Validated 2026 calendars only')
    while not session(day, calendar):
        day -= timedelta(days=1)
    return day


def session_age(reference: date, quote_date: date, calendar: str) -> int:
    if quote_date > reference:
        raise ValueError('Future quote')
    if not session(quote_date, calendar):
        raise ValueError('Quote not on a trading session')
    day = quote_date
    age = 0
    while day < last_session(reference, calendar):
        day += timedelta(days=1)
        if session(day, calendar):
            age += 1
    return age


def settlement(trade_date: date, lag: int, calendar: str) -> date:
    if lag < 0 or lag > 5:
        raise ValueError('Unsupported settlement lag')
    if not session(trade_date, calendar):
        raise ValueError('Trade date is not a trading session')
    # Settlement calendar differs from the trading calendar. Explicit TARGET
    # for EUR transactions, XNYS for USD illustration; not a fiscal cutoff.
    day = trade_date
    for _ in range(lag):
        day += timedelta(days=1)
        while not session(day, 'TARGET' if calendar in ('XMIL', 'XPAR', 'XETR') else calendar):
            day += timedelta(days=1)
    return day


def trade_timeline(trade_date: date, venue: str, lag: int):
    settle = settlement(trade_date, lag, venue)
    return {'trade_date': trade_date.isoformat(), 'settlement_date': settle.isoformat(),
            'fiscal_recognition_date': None, 'fiscal_status': 'INCOMPLETE',
            'note': 'Date of fiscal recognition requires account-specific validation'}
