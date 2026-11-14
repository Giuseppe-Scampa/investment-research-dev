"""Post-freeze failure diagnostics for V3 original as-of members.

These labels do not alter V3's locked _forward or its statistical gate:
they explain WHY a future outcome was not observed, without pretending
that a 16% equity crash is necessarily a split, that repeated closes prove
an exchange suspension, or that a delisting has a known cash payout.
"""
from __future__ import annotations

from datetime import date,timedelta
from decimal import Decimal

from .historical_calendar_v2 import dates_v2

REASONS=frozenset({
    "INSUFFICIENT_FUTURE_OBSERVATIONS",
    "MISSING_OR_DISCONTINUOUS_EXCHANGE_SESSION",
    "MISSING_NEXT_ENTRY_SESSION",
    "JUMP_GE15_PERCENT_CORPORATE_ACTION_OR_REAL_CRASH_UNRESOLVED",
    "ORIGINAL_ADJUSTMENT_OR_PRICE_PATH_UNVERIFIED",
})
STALE_THRESHOLD_CONSECUTIVE_CLOSES=5


def unresolved_reason(candidate, rows, decision_date, holding):
    """Classify only AFTER freezing rank and original cohort at decision T."""
    later=[r for r in rows if r[0]>decision_date]
    path=later[:holding+1]
    if len(path)!=holding+1:
        return "INSUFFICIENT_FUTURE_OBSERVATIONS"
    expected=dates_v2(date.fromisoformat(path[0][0]),
                      date.fromisoformat(path[-1][0]),candidate["venue"])
    if tuple(x[0] for x in path)!=expected:
        return "MISSING_OR_DISCONTINUOUS_EXCHANGE_SESSION"
    entry=dates_v2(date.fromisoformat(decision_date)+timedelta(days=1),
                   date.fromisoformat(path[0][0]),candidate["venue"])
    if entry!=(path[0][0],):
        return "MISSING_NEXT_ENTRY_SESSION"
    if any(abs(path[i][1]/path[i-1][1]-1)>=Decimal(".15")
           for i in range(1,len(path))):
        return "JUMP_GE15_PERCENT_CORPORATE_ACTION_OR_REAL_CRASH_UNRESOLVED"
    return "ORIGINAL_ADJUSTMENT_OR_PRICE_PATH_UNVERIFIED"


def stale_close_warning(candidate, rows, decision_date, holding):
    """Five or more identical closes are a warning, not proof of suspension.

    No venue status, official halt notice, liquidity or corporate-action
    statement is available from repeated adjusted closes alone.
    """
    path=[r for r in rows if r[0]>decision_date][:holding+1]
    if len(path)!=holding+1:
        return False
    run=1
    for left,right in zip(path,path[1:]):
        run = run+1 if left[1]==right[1] else 1
        if run>=STALE_THRESHOLD_CONSECUTIVE_CLOSES:
            return True
    return False
