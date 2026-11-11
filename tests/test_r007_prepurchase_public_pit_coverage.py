"""Fixed historical membership departure coverage: no vendor prices or contacts."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import preflight_historicaldata_departures_2021 as m


def test_public_coverage_schema_separates_no_match_from_outage_and_reused_ticker():
    base={"apiVersion":"2","stocks":{"found":True,"records":[
        {"file":"FAKE.csv","firstDate":"2020-01-03","lastDate":"2022-08-05",
         "delistDate":"2022-08-08"}]}}
    out=m.summarize_one_response(base)
    assert out["state"]=="FOUND_METADATA_ONLY"
    assert out["interval_spans_asof"] is True
    assert out["candidate_delisted"] is True
    assert out["multiple_listings"] is False
    base["stocks"]["records"].append({
        "file":"SAME_TICKER_DIFFERENT_LISTING.csv",
        "firstDate":"2024-01-02","lastDate":"2026-10-01"})
    assert m.summarize_one_response(base)["multiple_listings"] is True
    base["stocks"]={"found":False,"records":[]}
    assert m.summarize_one_response(base)["state"]=="NOT_FOUND"
    base["stocks"]={"unavailable":True}
    assert m.summarize_one_response(base)["state"]=="UNAVAILABLE"


@pytest.mark.parametrize("bad",[
    {"apiVersion":"2","stocks":{"found":True,"records":[]}},
    {"apiVersion":"2","stocks":{"found":True,"records":[
        {"firstDate":"2024-01-01","lastDate":"2023-01-01"}]}},
    {"apiVersion":"2","stocks":{"found":True,"records":[
        {"firstDate":"2024-01-01"}]}},
    {"apiVersion":"1","stocks":{"found":False,"records":[]}},
])
def test_invalid_ticker_dates_or_schema_fail_closed(bad):
    with pytest.raises(ValueError):
        m.summarize_one_response(bad)


def test_pit_membership_source_is_pinned_not_provider_free_text():
    raw=b"ticker,start_date,end_date\nA,2020-01-01,2024-01-01\n"
    with pytest.raises(ValueError,match="SHA changed"):
        m.frozen_intervals(raw)
    blob=b"blob "+str(len(raw)).encode()+b"\x00"+raw
    original=m.PIT_GIT_BLOB
    try:
        m.PIT_GIT_BLOB=hashlib.sha1(blob).hexdigest()
        rows=m.frozen_intervals(raw)
        assert m.members_at(rows,"2021-01-01")=={"A"}
        assert m.members_at(rows,"2026-01-01")==set()
    finally:
        m.PIT_GIT_BLOB=original


def test_departure_count_cannot_be_forged(monkeypatch):
    intervals=[("ABC","2020-01-01","2022-01-01")]
    monkeypatch.setattr(m,"EXPECTED_MISSING_2021_FROM_2026",95)
    with pytest.raises(ValueError,match="membership size"):
        m.prior_departures(intervals)
