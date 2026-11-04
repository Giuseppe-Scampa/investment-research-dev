"""R-004/R-005 Alpha Vantage diagnostic: all fixtures synthetic and offline."""
from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime, timedelta, timezone

import pytest

from investresearch import research_alpha_pilot as av
from investresearch.research_cli import main


NOW = datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)
ASOF = date(2026, 11, 4)


def sample_response(*, symbol="FRE", n=67, change=None):
    series={}
    day=ASOF
    while len(series)<n:
        if day.weekday()<5:
            i=len(series)
            series[day.isoformat()]={
                "1. open":str(100+i/100), "2. high":str(101+i/100),
                "3. low":str(99+i/100), "4. close":str(100+i/100),
                "5. volume":"190000",
            }
        day-=timedelta(days=1)
    payload={
        "Meta Data":{
            "1. Information":"Daily Prices (open, high, low, close) and Volumes",
            "2. Symbol":symbol,
            "3. Last Refreshed":ASOF.isoformat(),
            "4. Output Size":"Compact",
        },
        "Time Series (Daily)":series,
    }
    if change: change(payload)
    return json.dumps(payload).encode("utf-8")


def test_parse_raw_compact_daily_source_keeps_ohlcv_order_and_labels():
    rows=av.parse_daily(sample_response(), "FRE", ASOF)
    assert len(rows)==67
    assert rows[0]["Date"]<rows[-1]["Date"]
    assert rows[-1]["Date"]=="2026-11-04"
    assert rows[-1]["Volume"]=="190000"
    assert set(rows[-1])==set(av.CSV_FIELDS)


@pytest.mark.parametrize("change,match", [
    (lambda p: p["Meta Data"].update({"2. Symbol":"ANOTHER"}), "does not match"),
    (lambda p: p.update({"Note":"API rate limit reached"}), "rate-limit"),
    (lambda p: p.update({"Information":"Premium endpoint required"}), "rate-limit"),
    (lambda p: p["Time Series (Daily)"][ASOF.isoformat()].update({"2. high":"50"}), "high inconsistent"),
    (lambda p: p["Time Series (Daily)"][ASOF.isoformat()].update({"3. low":"130"}), "low inconsistent"),
    (lambda p: p["Time Series (Daily)"][ASOF.isoformat()].update({"4. close":"NaN"}), "non-finite"),
    (lambda p: p["Time Series (Daily)"][ASOF.isoformat()].update({"5. volume":"1.5"}), "not an integer"),
    (lambda p: p["Time Series (Daily)"][ASOF.isoformat()].update({"bad":"0"}), "malformed"),
    (lambda p: p["Meta Data"].update({"3. Last Refreshed":"2026-11-05"}), "future"),
    (lambda p: p["Time Series (Daily)"].update({"2026-11-05":{
       "1. open":"100", "2. high":"101", "3. low":"99",
       "4. close":"100", "5. volume":"2000"}}), "Future"),
])
def test_parser_rejects_broken_provider_metadata_ohlcv_and_future(change,match):
    with pytest.raises(ValueError,match=match):
        av.parse_daily(sample_response(change=change),"FRE",ASOF)


def test_pilot_detects_json_duplicate_fields_and_nonjson_errors():
    with pytest.raises(ValueError,match="Duplicate JSON"):
        av.parse_daily(b'{"Meta Data":{},"Meta Data":{}}',"ABC",ASOF)
    with pytest.raises(ValueError,match="Malformed"):
        av.parse_daily(b'{',"ABC",ASOF)
    with pytest.raises(ValueError,match="documented daily series"):
        av.parse_daily(b'{"Meta Data":{}}',"ABC",ASOF)
    with pytest.raises(ValueError,match="size"):
        av.parse_daily(b"x"*(av.MAX_RESPONSE_BYTES+1),"ABC",ASOF)
    with pytest.raises(ValueError,match="Invalid explicit symbol"):
        av.parse_daily(sample_response(),"../../secret",ASOF)


def test_pilot_keeps_key_out_of_disk_and_reports_and_refuses_overwrite(tmp_path):
    sent=[]
    def fake_transport(url):
        sent.append(url)
        return sample_response(symbol="IBM")
    key="VERY_PRIVATE_TEST_KEY_42"
    kwargs=dict(
        symbol="IBM",venue="XNYS",as_of=ASOF,
        repo_root=tmp_path/"repo",
        output=tmp_path/"repo"/"data"/"private"/"av_pilot",
        api_key=key,
        live_confirm=True,
        terms_confirm=True,retrieved_at_utc=NOW,
        transport=fake_transport,
    )
    result=av.run_pilot(**kwargs)
    assert len(sent)==1
    assert "function=TIME_SERIES_DAILY" in sent[0]
    assert "outputsize=compact" in sent[0]
    assert result["session_count"]==67
    assert result["research_status"]=="NOT_TRADE_READY_NOT_ELIGIBLE_FOR_GLOBAL_FUNNEL"
    assert result["isin"]=="UNVERIFIED_NOT_RETURNED_BY_PROVIDER"
    assert result["license"]=="NOT_VERIFIED_FOR_AUTOMATED_RANKING_OR_DISTRIBUTION"
    metadata=(kwargs["output"]/"ALPHA_PILOT_METADATA.json").read_text()
    csv=(kwargs["output"]/"ALPHA_DAILY_UNVERIFIED.csv").read_text()
    assert key not in metadata+csv
    assert "apikey=" not in metadata
    assert csv.startswith("Date,Open,High,Low,Close,Volume\n")
    assert len(result["raw_payload_sha256"])==64
    with pytest.raises(ValueError,match="overwrite"):
        av.run_pilot(**kwargs)
    assert len(sent)==1  # Do not consume second request to overwrite outputs


def test_explicit_consent_required_without_touching_network(tmp_path):
    def forbidden(url):
        raise AssertionError("unauthorized network")
    base=dict(
        symbol="IBM",venue="XNYS",as_of=ASOF,
        repo_root=tmp_path,output=tmp_path/"data"/"private"/"pilot",
        api_key="fake",retrieved_at_utc=NOW,transport=forbidden,
    )
    with pytest.raises(ValueError,match="confirmation"):
        av.run_pilot(**base)
    with pytest.raises(ValueError,match="confirmation"):
        av.run_pilot(**base,live_confirm=True)
    with pytest.raises(ValueError,match="MIC"):
        av.run_pilot(**base,live_confirm=True,terms_confirm=True,venue="UNKNOWN")


def test_pilot_refuses_backdated_source_and_public_repository_outputs(tmp_path):
    fake=lambda url:sample_response(symbol="IBM")
    base=dict(
        symbol="IBM",venue="XNYS",as_of=ASOF,
        repo_root=tmp_path/"repo",output=tmp_path/"repo"/"reports"/"generated"/"pilot",
        api_key="fake",retrieved_at_utc=NOW,transport=fake,
        live_confirm=True,terms_confirm=True,
    )
    with pytest.raises(ValueError,match="data/private"):
        av.run_pilot(**base)
    base["output"]=tmp_path/"repo"/"data"/"private"/"pilot"
    base["as_of"]=date(2026,11,3)
    with pytest.raises(ValueError,match="today"):
        av.run_pilot(**base)
    base["as_of"]=ASOF
    base["retrieved_at_utc"]=datetime(2026,11,4,14,20)
    with pytest.raises(ValueError,match="UTC-aware"):
        av.run_pilot(**base)


def test_api_key_is_environment_only_and_url_is_fixed():
    from urllib.parse import parse_qs, urlsplit
    url=av._url("IBM","a_test_key")
    parsed=urlsplit(url)
    assert (parsed.scheme,parsed.hostname,parsed.path)==(
        "https","www.alphavantage.co","/query")
    args=parse_qs(parsed.query)
    assert args["function"]==["TIME_SERIES_DAILY"]
    assert args["outputsize"]==["compact"]
    assert args["apikey"]==["a_test_key"]
    for bad in ("../priv","bad/abc","with spaces","a"*21):
        with pytest.raises(ValueError,match="symbol"):
            av._url(bad,"a_test_key")
    with pytest.raises(ValueError,match="key"):
        av._url("IBM","")


def test_cli_enforces_live_confirmation_before_api_key_or_network(tmp_path,monkeypatch,capsys):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY",raising=False)
    base=["alpha-pilot","--symbol","IBM","--venue","XNYS",
          "--as-of","2026-11-04","--output",str(tmp_path/"pilot")]
    with pytest.raises(SystemExit) as err:
        main(base)
    assert err.value.code==2
    assert "live-confirm" in capsys.readouterr().err
