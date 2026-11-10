"""Independently pinned multi-year research sessions, not tax settlement."""
from datetime import date,timedelta
import pytest

from investresearch.validated_multiyear_calendar import (
    session_historical,previous_common_session,subsequent_sessions,
)


@pytest.mark.parametrize("venue",["XMIL","XPAR","XETR","XNYS","XNAS","XAMS","XBRU","XDUB"])
def test_2022_2026_calendar_scope_is_explicit_and_market_specific(venue):
    assert session_historical(date(2023,1,3),venue)
    assert not session_historical(date(2024,1,6),venue)
    with pytest.raises(ValueError,match="2022"):
        session_historical(date(2021,12,31),venue)
    with pytest.raises(ValueError,match="2022"):
        session_historical(date(2027,1,4),venue)


@pytest.mark.parametrize("venue,day,expected",[
    ("XNYS","2022-06-20",False), # Juneteenth observed
    ("XNYS","2023-07-04",False), # Independence Day
    ("XNYS","2024-03-29",False), # Good Friday
    ("XMIL","2023-04-10",False), # Easter Monday
    ("XPAR","2024-05-01",False), # Labour Day
    ("XETR","2025-12-24",False), # Christmas Eve
    ("XAMS","2025-12-25",False),
])
def test_representative_historical_exchange_holiday(venue,day,expected):
    assert session_historical(date.fromisoformat(day),venue)==expected


def test_common_date_and_true_session_count():
    anchor=previous_common_session(date(2024,1,1),["XNYS","XMIL","XETR"])
    assert anchor<date(2024,1,1)
    assert all(session_historical(anchor,x) for x in ("XNYS","XMIL","XETR"))
    next_30=subsequent_sessions(anchor,"XMIL",30)
    assert len(next_30)==30 and len(set(next_30))==30
    assert all(session_historical(d,"XMIL") for d in next_30)
    assert all(next_30[i]<next_30[i+1] for i in range(29))
    with pytest.raises(ValueError,match="Unsupported"):
        session_historical(date(2024,1,3),"TARGET")
