"""Pre-purchase aggregate *metadata-only* coverage check for PIT delisted S&P names.

This code calls a publicly documented REST COVERAGE endpoint; it does
not download prices, join historical returns, buy a product, expose ticker
identifiers, or imply that matching dates prove security identity/settlement.
Original PIT memberships are pinned to a MIT-licensed public commit.
No use of premium data or paid EODHD.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from datetime import date,timedelta
from urllib.error import HTTPError,URLError
from urllib.parse import quote
from urllib.request import Request,urlopen

PIT_BASE="https://raw.githubusercontent.com/kitata2/8765_sp500_pit/"
PIT_COMMIT="830c0128fc585131ede9d722958214e1208ff0fa"
PIT_PATH="sp500_ticker_start_end.csv"
PIT_GIT_BLOB="3ed3b0e8d9e6e63730c153ee1f13ddaf6ed281bb"
LOOKUP_BASE="https://historicaldata.net/api/symbol/"
EXPECTED_MISSING_2021_FROM_2026=95
START="2021-07-01"
END="2026-08-18"
USER_AGENT="Research-coverage-check/1.0 (public metadata only, no price download)"
REQUEST_SPACING_SECONDS=0.6
MAX_PUBLIC_METADATA_REQUESTS=100
MAX_JSON_BYTES=80_000


def _fetch_public(url,max_bytes=100_000):
    request=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json" if "api/symbol/" in url else "text/csv"})
    with urlopen(request,timeout=15) as r:
        if r.status!=200:
            raise ValueError("Public metadata source non-200 response")
        if (length:=r.headers.get("Content-Length")) and int(length)>max_bytes:
            raise ValueError("Public metadata exceeded declared safe bound")
        payload=r.read(max_bytes+1)
    if len(payload)>max_bytes:
        raise ValueError("Public metadata response exceeded maximum size")
    return payload


def frozen_intervals(payload):
    blob=b"blob "+str(len(payload)).encode()+b"\x00"+payload
    if hashlib.sha1(blob).hexdigest()!=PIT_GIT_BLOB:
        raise ValueError("Original MIT index-membership source SHA changed")
    rdr=csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if rdr.fieldnames!=["ticker","start_date","end_date"]:
        raise ValueError("Historical PIT ticker interval schema drift")
    intervals=[]
    for x in rdr:
        start,end=x["start_date"],x["end_date"] or None
        date.fromisoformat(start)
        if end:date.fromisoformat(end)
        intervals.append((x["ticker"],start,end))
    return intervals


def members_at(intervals,as_of):
    date.fromisoformat(as_of)
    return {ticker for ticker,start,end in intervals
            if start<=as_of and (end is None or as_of<=end)}


def prior_departures(intervals):
    start=members_at(intervals,START)
    end=members_at(intervals,END)
    gone=sorted(start-end)
    if len(gone)!=EXPECTED_MISSING_2021_FROM_2026:
        raise ValueError("Historical PIT provider membership size differs from registered audit")
    return gone


def departure_exit_calendar_dates(intervals):
    """Membership spells active at START, before seeing vendor price metadata."""
    gone=set(prior_departures(intervals))
    ended={}
    for ticker,started,last in intervals:
        if ticker in gone and started<=START and (last is None or last>=START):
            if not last or ticker in ended:
                raise ValueError("PIT historical 2021 member had missing/ambiguous exit spell")
            ended[ticker]=last
    if set(ended)!=gone:
        raise ValueError("Could not match all original exited membership spells")
    return ended


def summarize_one_response(document,as_of=START):
    """Return only public coverage *flags*, not issuer data or source rows."""
    if not isinstance(document,dict) or document.get("apiVersion") not in ("2",2):
        raise ValueError("Malformed or unversioned public provider metadata")
    stocks=document.get("stocks")
    if not isinstance(stocks,dict) or stocks.get("unavailable") is True:
        return {"state":"UNAVAILABLE","multiple_listings":False,
                "interval_spans_asof":False,"candidate_delisted":False,
                "matching_listing_last_date":None}
    records=stocks.get("records")
    if not isinstance(records,list):
        raise ValueError("Published provider stock schema missing records")
    if not records:
        if stocks.get("found") is not False:
            raise ValueError("Empty records without explicit public not-found")
        return {"state":"NOT_FOUND","multiple_listings":False,
                "interval_spans_asof":False,"candidate_delisted":False,
                "matching_listing_last_date":None}
    valid=0
    matching_last_date=None
    candidate_delisted=False
    for rec in records:
        if not isinstance(rec,dict):
            raise ValueError("Malformed single-listing public metadata")
        a,b=rec.get("firstDate"),rec.get("lastDate")
        if not isinstance(a,str) or not isinstance(b,str):
            raise ValueError("Missing public listing date boundaries")
        date.fromisoformat(a)
        date.fromisoformat(b)
        if a>b:
            raise ValueError("Public listing has impossible date sequence")
        if a<=as_of<=b:
            valid+=1
            if matching_last_date is None or b>matching_last_date:
                matching_last_date=b
        candidate_delisted|=bool(rec.get("delistDate"))
    return {
        "state":"FOUND_METADATA_ONLY",
        "multiple_listings":len(records)>1,
        "interval_spans_asof":valid>0,
        "candidate_delisted":candidate_delisted,
        "matching_listing_last_date":matching_last_date,
    }


def coverage_audit(members_payload,fetch_metadata=_fetch_public):
    intervals=frozen_intervals(members_payload)
    missing=prior_departures(intervals)
    by_membership_exit=departure_exit_calendar_dates(intervals)
    if len(missing)>MAX_PUBLIC_METADATA_REQUESTS:
        raise ValueError("Too many metadata checks; adjust scope rather than rate limits")
    counts={x:0 for x in (
        "FOUND_METADATA_ONLY","NOT_FOUND","UNAVAILABLE")}
    spans=0;reused=0;delisted_markers=0;error_count=0
    spans_to_end=0;ends_within_week=0;ends_earlier=0
    fingerprints=[]
    for i,ticker in enumerate(missing):
        if i:time.sleep(REQUEST_SPACING_SECONDS)
        uri=LOOKUP_BASE+quote(ticker,safe="")+"?product=stocks"
        try:
            raw=fetch_metadata(uri)
            entry=summarize_one_response(json.loads(raw))
            fingerprints.append(hashlib.sha256(raw).hexdigest())
        except (HTTPError,URLError,OSError,ValueError,KeyError,UnicodeError):
            entry={"state":"UNAVAILABLE","multiple_listings":False,
                   "interval_spans_asof":False,"candidate_delisted":False,
                   "matching_listing_last_date":None}
            error_count+=1
        counts[entry["state"]]+=1
        spans+=int(entry["interval_spans_asof"])
        reused+=int(entry["multiple_listings"])
        delisted_markers+=int(entry["candidate_delisted"])
        last=entry["matching_listing_last_date"]
        if last:
            exit_day=date.fromisoformat(by_membership_exit[ticker])
            last_day=date.fromisoformat(last)
            if last_day>=exit_day:
                spans_to_end+=1
            elif last_day>=exit_day-timedelta(days=7):
                ends_within_week+=1
            else:
                ends_earlier+=1
    if sum(counts.values())!=len(missing):
        raise ValueError("Historical ticker numerator/denominator mismatch")
    return {
        "schema_version":"PIT_2021_DEPARTURE_PUBLIC_COVERAGE_METADATA_V1",
        "source_membership_commit":PIT_COMMIT,
        "source_membership_git_blob":PIT_GIT_BLOB,
        "historical_asof_start":START,
        "historical_comparison_end":END,
        "departed_historical_symbol_count":len(missing),
        "provider_public_metadata_found":counts["FOUND_METADATA_ONLY"],
        "provider_public_metadata_not_found":counts["NOT_FOUND"],
        "provider_unavailable_or_error":counts["UNAVAILABLE"],
        "public_listing_file_spans_2021_asof_date":spans,
        "metadata_listing_extends_to_or_after_historical_index_exit":spans_to_end,
        "metadata_listing_ends_within_week_before_historical_exit":ends_within_week,
        "metadata_listing_ends_more_than_week_before_exit":ends_earlier,
        "tickers_with_multiple_published_listing_lifetimes":reused,
        "metadata_records_with_delisting_date":delisted_markers,
        "public_network_errors":error_count,
        "metadata_version_fingerprints_sha256":hashlib.sha256(
            "\n".join(fingerprints).encode()).hexdigest(),
        "not_equivalent_to_exact_2021_2026_daily_price_coverage":True,
        "not_equivalent_to_stable_security_identity_or_issuer":True,
        "not_equivalent_to_verified_delisting_payout":True,
        "no_paid_market_data_requested":True,
        "no_price_or_individual_ticker_published":True,
        "source_rights_and_actual_price_quality_unverified":True,
        "ready_for_trade":False,
    }


def main():
    try:
        raw=_fetch_public(PIT_BASE+PIT_COMMIT+"/"+PIT_PATH,150_000)
        result=coverage_audit(raw)
    except (HTTPError,URLError,OSError,ValueError,KeyError,UnicodeError) as exc:
        print("HISTORICAL_PROVIDER_PREPURCHASE_METADATA_UNAVAILABLE",
              type(exc).__name__,"NO_PRICE_OR_DELISTER_RETURN_CERTIFIED")
        return 3
    print("PUBLIC_METADATAS_ONLY_PIT_DEPARTURES_COVERAGE_NOT_TRADING_DATA")
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
