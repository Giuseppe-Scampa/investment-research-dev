"""Multi-year research exchange sessions, separate from 2026 tax settlements.

Pinned exchange_calendars 4.13.1 rulebook. 2022–2026 only.
No calendar inference for unsupported markets, no fiscal-recognition claims.
"""
from __future__ import annotations

from datetime import date,timedelta
from functools import lru_cache

SUPPORTED={
    "XMIL":"XMIL","XPAR":"XPAR","XETR":"XETR",
    "XNYS":"XNYS","XNAS":"XNYS",
    "XAMS":"XAMS","XBRU":"XBRU","XDUB":"XDUB",
}
START=date(2022,1,1)
END=date(2026,12,31)
PINNED_VERSION="4.13.1"


@lru_cache(maxsize=9)
def _get_calendar(venue):
    if venue not in SUPPORTED:
        raise ValueError("Unsupported historical venue; no guessed calendar")
    import exchange_calendars
    if exchange_calendars.__version__!=PINNED_VERSION:
        raise ValueError("Unreviewed exchange_calendars version")
    return exchange_calendars.get_calendar(SUPPORTED[venue])


def session_historical(day:date,venue:str)->bool:
    if not START<=day<=END:
        raise ValueError("Multi-year research calendar validated only for 2022–2026")
    cal=_get_calendar(venue)
    # exchange_calendars weekend and observed holiday handling is
    # exchange-specific. Do not treat this as verified auction/fill evidence.
    return bool(cal.is_session(day.isoformat()))


def previous_common_session(anchor,venues):
    if not venues or len(set(venues))>8:
        raise ValueError("Explicit bounded market universe required")
    cursor=anchor
    for _ in range(11):
        if all(session_historical(cursor,v) for v in venues):
            return cursor
        cursor-=timedelta(days=1)
        if cursor<START:
            break
    raise ValueError("No verified common exchange date within eleven days")


def subsequent_sessions(day,venue,count):
    if count<1 or count>125:
        raise ValueError("Historical forward trading sessions must be bounded")
    found=[]
    current=day
    while len(found)<count:
        current+=timedelta(days=1)
        if current>END:
            raise ValueError("Future session exceeds validated 2026 research scope")
        if session_historical(current,venue):
            found.append(current)
    return found
