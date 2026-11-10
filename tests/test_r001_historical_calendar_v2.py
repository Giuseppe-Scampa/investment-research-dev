"""V2 exchange-calendar regression; original V1 tax calendar is untouched."""
from datetime import date
import pytest
from investresearch.historical_calendar_v2 import session_v2,dates_v2


@pytest.mark.parametrize("venue",["XNYS","XNAS","XETR","XMIL","XPAR"])
def test_multiyear_calendar_rejects_good_friday_and_christmas(venue):
    assert session_v2(date(2024,3,29),venue) is False
    assert session_v2(date(2023,12,25),venue) is False
    assert session_v2(date(2024,3,28),venue) is True
    assert len(dates_v2(date(2021,1,1),date(2025,12,31),venue))>1200


def test_historical_calendars_reject_outside_range_and_unknown_venue():
    for d,v in [(date(2019,12,31),"XMIL"),(date(2027,1,4),"XNYS"),
                (date(2024,4,1),"INVALID")]:
        with pytest.raises(ValueError):
            session_v2(d,v)


def test_v1_2026_immutability_is_not_replaced_by_v2():
    from investresearch.market_calendar import session
    with pytest.raises(ValueError,match="2026"):
        session(date(2024,3,28),"XMIL")
    assert session_v2(date(2024,3,28),"XMIL") is True
