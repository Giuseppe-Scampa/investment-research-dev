"""Audited PIT *membership-only* coverage for the first real-source pilot.

No stock prices are used or downloaded. Cross-checks the November 2026
current-survivor 40-name cohort against a frozen MIT-licensed HISTORICAL
membership snapshot. Public logs contain aggregate counts, not tickers.

Historical membership is community curated and has ticker-reuse limitations;
it is NOT an independently certified CRSP/official S&P Dow Jones panel.
This diagnostic does not change any V1/V2/V3 registered backtest or
attempt to infer unavailable delisting proceeds.
"""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pilot_real_sp500_backtest_v2 as prior
from investresearch.research_historical_validation_v2 import preregistered_anchors
from investresearch.research_historical_validation_v3 import v3_protocol

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"config/backtest/v3_secondary_real_history_pilot_2026-11-10.json"
CURRENT_ROSTER_SHA256="853f2fe3c4b126b6b251dbc7c81510de22c17167f2c0e646212e38e1cc45420f"
MIT_PIT_COMMIT="830c0128fc585131ede9d722958214e1208ff0fa"
MIT_PIT_GIT_BLOB="3ed3b0e8d9e6e63730c153ee1f13ddaf6ed281bb"
MIT_PIT_URL=("https://raw.githubusercontent.com/kitata2/8765_sp500_pit/"
             +MIT_PIT_COMMIT+"/sp500_ticker_start_end.csv")
LICENSE_URL="https://github.com/kitata2/8765_sp500_pit/blob/"+MIT_PIT_COMMIT+"/LICENSE"
CURRENT_DATE="2026-08-18"
BASELINE_DATE="2021-07-01"


def parse_mit_member_intervals(payload:bytes):
    if (len(payload)>1_000_000 or not payload
            or hashlib.sha1(b"blob "+str(len(payload)).encode()+b"\\x00"+payload).hexdigest()
               !=MIT_PIT_GIT_BLOB):
        raise ValueError("Original public MIT PIT membership source changed")
    rows=csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if rows.fieldnames!=["ticker","start_date","end_date"]:
        raise ValueError("MIT PIT membership date interval schema changed")
    segments=[]
    seen=set()
    for row in rows:
        symbol=row["ticker"]
        start=row["start_date"]
        end=row["end_date"] or None
        if (not symbol or not start or date.fromisoformat(start)>date.fromisoformat(end or "2100-01-01")
                or (symbol,start,end) in seen):
            raise ValueError("Duplicated or ill-formed original membership spell")
        seen.add((symbol,start,end))
        segments.append((symbol,start,end))
    return segments


def members_on(segments,day):
    if not isinstance(day,str):
        raise ValueError("Date must be ISO string")
    date.fromisoformat(day)
    return {symbol for symbol,start,end in segments
            if start<=day and (end is None or day<=end)}


def membership_quality_only(original_current_roster,mit_membership):
    if hashlib.sha256(original_current_roster).hexdigest()!=CURRENT_ROSTER_SHA256:
        raise ValueError("Original current-company source vintage changed: fail-closed")
    policy=json.loads(POLICY.read_text())
    selection,source_counts=prior.select_cohort(original_current_roster,policy)
    if len(selection)!=40 or len(set(selection))!=40:
        raise ValueError("Previously registered original sampled research cohort changed")
    historical=parse_mit_member_intervals(mit_membership)
    old=members_on(historical,BASELINE_DATE)
    later=members_on(historical,CURRENT_DATE)
    union={name for name,start,end in historical
           if start<=CURRENT_DATE and (end is None or end>=BASELINE_DATE)}
    removed=old-later
    new=later-old
    anchors=preregistered_anchors(["XNYS"],v3_protocol()[0])
    daily_sample_counts=[(t,len(set(selection)&members_on(historical,t)))
                         for t in anchors if BASELINE_DATE<=t<=CURRENT_DATE]
    return {
        "schema_version":"S_P500_HISTORICAL_MEMBERSHIP_DIAGNOSTIC_V1",
        "type":"MEMBERSHIP_ONLY_NO_PRICE_OR_PERFORMANCE_RUN",
        "input_current_company_sha256":hashlib.sha256(original_current_roster).hexdigest(),
        "input_mit_pit_membership_sha256":hashlib.sha256(mit_membership).hexdigest(),
        "input_mit_pit_commit":MIT_PIT_COMMIT,
        "sample_original_current_survivors":len(selection),
        "date_start":BASELINE_DATE,
        "date_end":CURRENT_DATE,
        "historical_s_and_p_members_at_start":len(old),
        "historical_s_and_p_members_at_end":len(later),
        "historical_unique_members_over_period":len(union),
        "start_members_absent_at_end":len(removed),
        "end_members_not_in_start_membership":len(new),
        "original_pilot_sample_member_count_min_across_historical_anchors":min(
            (n for _,n in daily_sample_counts),default=None),
        "original_pilot_sample_member_count_max_across_historical_anchors":max(
            (n for _,n in daily_sample_counts),default=None),
        "registered_asof_anchor_dates_crosschecked":len(daily_sample_counts),
        "original_sample_has_current_membership_hindsight":True,
        "removed_historical_members_have_priced_terminal_outcomes":False,
        "historical_prices_or_original_ISIN_or_delisting_events_verified":False,
        "historical_spells_are_community_curated_ticker_not_stable_issuer_ID":True,
        "available_for_validating_original_backtest_alpha":False,
        "trade_ready":False,
    }


def fetch_mit_roster():
    original=prior._fetch(MIT_PIT_URL,1_000_000)
    parse_mit_member_intervals(original)
    return original


def main():
    try:
        current=prior._fetch(json.loads(POLICY.read_text())["source_current_members_csv"],300_000)
        historical=fetch_mit_roster()
        summary=membership_quality_only(current,historical)
    except (OSError,ValueError,UnicodeError,KeyError,TimeoutError) as exc:
        print("PIT_HISTORY_SOURCE_VINTAGE_OR_ACCESS_BLOCKED",
              type(exc).__name__,"NO_HINDSIGHT_COHORT_RECLASSIFICATION")
        return 3
    print("HISTORICAL_MEMBERSHIP_DIAGNOSTIC_ONLY_NOT_A_NEW_BACKTEST")
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
