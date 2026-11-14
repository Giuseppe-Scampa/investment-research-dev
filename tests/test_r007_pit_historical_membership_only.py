"""No-network PIT membership-only regression tests; no real market data."""
from datetime import date
import hashlib
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import audit_secondary_sp500_pit_membership as m


def _freeze_sample(monkeypatch,raw):
    blob=b"blob "+str(len(raw)).encode()+b"\x00"+raw
    monkeypatch.setattr(m,"MIT_PIT_GIT_BLOB",hashlib.sha1(blob).hexdigest())


def test_historical_membership_snapshot_can_change_issuer_presence(monkeypatch):
    raw=(b"ticker,start_date,end_date\n"
         b"OLD,2020-01-01,2023-01-02\n"
         b"NEW,2023-01-03,\n"
         b"REJOIN,2020-01-01,2021-03-10\n"
         b"REJOIN,2024-01-02,\n")
    _freeze_sample(monkeypatch,raw)
    segments=m.parse_mit_member_intervals(raw)
    assert m.members_on(segments,"2021-03-09")=={"OLD","REJOIN"}
    assert m.members_on(segments,"2023-02-01")=={"NEW"}
    assert m.members_on(segments,"2025-01-01")=={"NEW","REJOIN"}


def test_corrupted_original_source_fail_closed_without_silent_rebase(monkeypatch):
    raw=b"ticker,start_date,end_date\nA,2020-01-01,\n"
    with pytest.raises(ValueError,match="changed"):
        m.parse_mit_member_intervals(raw)
    _freeze_sample(monkeypatch,raw)
    assert len(m.parse_mit_member_intervals(raw))==1
    for tamper in (raw.replace(b"2020",b"2021"),
                   b"ticker,start_date,end_date\nA,2020-01-01,2021-01-01\n"):
        with pytest.raises(ValueError,match="changed"):
            m.parse_mit_member_intervals(tamper)


def test_current_membership_vintage_mismatch_is_blocked_before_sampling():
    raw=b"ticker,name,sector,industry,headquarters,date_added,cik,founded\n"
    with pytest.raises(ValueError,match="source vintage changed"):
        m.membership_quality_only(raw,b"NO_HISTORICAL_SOURCE")
