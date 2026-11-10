"""Isolated historical-session adapter for preregistered V2 evaluation.

Does NOT alter M1's frozen 2026 tax/settlement calendar. This source is an
auditable third-party exchange calendar MODEL, not official exchange proof.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

LIB_VERSION="4.13.1"
VENUES=frozenset({"XNYS","XNAS","XMIL","XPAR","XETR"})
START=date(2020,1,1)
END=date(2026,12,31)


@lru_cache(maxsize=5)
def _calendar(venue):
    if venue not in VENUES:
        raise ValueError("Unsupported V2 historical exchange venue")
    try:
        import exchange_calendars as xcals
    except ImportError:
        raise ValueError("V2 needs explicitly pinned exchange_calendars==4.13.1") from None
    if xcals.__version__!=LIB_VERSION:
        raise ValueError("V2 exchange calendar version changed; compare/approve new release before running")
    return xcals.get_calendar(venue,start="2019-12-20",end="2027-01-05")


def session_v2(day: date,venue: str)->bool:
    if not isinstance(day,date) or not START<=day<=END:
        raise ValueError("V2 calendar outside independently tested 2020–2026 window")
    return bool(_calendar(venue).is_session(day.isoformat()))


def dates_v2(start: date,end: date,venue: str)->tuple[str,...]:
    """Use a single cached exchange calendar, avoid repeated construction."""
    if (not isinstance(start,date) or not isinstance(end,date) or
            start<START or end>END or start>end or venue not in VENUES):
        raise ValueError("V2 calendar date range or venue not supported")
    return tuple(str(day.date()) for day in
                 _calendar(venue).sessions_in_range(start.isoformat(),end.isoformat()))
