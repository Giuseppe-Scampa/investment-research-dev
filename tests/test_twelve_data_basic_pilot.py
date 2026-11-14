"""Twelve Data Basic opt-in probe: strictly synthetic response fixtures/offline."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from investresearch import research_twelve_pilot as td
from investresearch.research_cli import main

TODAY=date(2026,11,5)
NOW=datetime(2026,11,5,9,30,tzinfo=timezone.utc)


def payload(symbol="FSLR",mic="XNAS",n=70,modifier=None):
    cur=TODAY
    values=[]
    while len(values)<n:
        if cur.weekday()<5:
            values.append({"datetime":cur.isoformat(),
                "open":"100","high":"102","low":"98","close":"101",
                "volume":"123456"})
        cur-=timedelta(days=1)
    data={"meta":{"symbol":symbol,"interval":"1day","mic_code":mic,
                  "currency":"USD","type":"Common Stock",
                  "exchange":"NASDAQ"},
          "values":values,"status":"ok"}
    if modifier:modifier(data)
    return json.dumps(data).encode("utf-8")


def test_parser_us_split_request_unverified_not_fictional_ready():
    bars,meta=td.parse_time_series(payload(),symbol="FSLR",venue="XNAS",as_of=TODAY)
    assert len(bars)==70
    assert bars[0]["date"]<bars[-1]["date"]
    assert bars[-1]["date"]==TODAY.isoformat()
    assert meta["provider_type"]=="Common Stock"


@pytest.mark.parametrize("modifier,match",[
    (lambda d:d["meta"].update({"symbol":"OTHER"}),"symbol mismatch"),
    (lambda d:d["meta"].update({"mic_code":"XNYS"}),"venue/interval mismatch"),
    (lambda d:d["meta"].update({"currency":"EUR"}),"Currency mismatch"),
    (lambda d:d.update({"status":"error","message":"API limit"}),"entitlement"),
    (lambda d:d["values"][0].update({"high":"90"}),"Invalid OHLC"),
    (lambda d:d["values"][0].update({"low":"110"}),"Invalid OHLC"),
    (lambda d:d["values"][0].update({"close":"NaN"}),"Invalid price"),
    (lambda d:d["values"][0].update({"volume":"4.4"}),"Noninteger"),
    (lambda d:d["values"][0].update({"datetime":"2026-11-06"}),"Future/duplicate"),
    (lambda d:d["values"].append(d["values"][0].copy()),"Future/duplicate"),
])
def test_reject_wrong_venue_entitlement_broken_market_bar(modifier,match):
    with pytest.raises(ValueError,match=match):
        td.parse_time_series(payload(modifier=modifier),symbol="FSLR",
                             venue="XNAS",as_of=TODAY)


def test_response_errors_and_size_duplicates():
    for raw,match in [
        (b'{"meta":{},"meta":{}}',"Duplicate"),
        (b'{',"Malformed"),
        (b'[]',"JSON object"),
        (b'x'*(td.MAX_BYTES+1),"oversized"),
    ]:
        with pytest.raises(ValueError,match=match):
            td.parse_time_series(raw,symbol="FSLR",venue="XNAS",as_of=TODAY)


def test_safe_url_restricts_provider_and_private_key():
    from urllib.parse import parse_qs,urlsplit
    url=td._url("FSLR","XNAS","secret_test_key")
    o=urlsplit(url)
    assert (o.scheme,o.hostname,o.path)==("https","api.twelvedata.com","/time_series")
    q=parse_qs(o.query)
    assert q["adjust"]==["splits"]
    assert q["interval"]==["1day"]
    assert q["outputsize"]==["100"]
    assert q["mic_code"]==["XNAS"]
    for symbol in ("a/b","A B","@bad","a"*20):
        with pytest.raises(ValueError):
            td._url(symbol,"XNAS","abc")
    with pytest.raises(ValueError):
        td._url("FSLR","XNAS","")
    with pytest.raises(ValueError):
        td._url("FSLR","XMIL","abc")


def test_private_single_download_no_secrets_and_no_overwrite(tmp_path):
    urls=[]
    def transport(url):
        urls.append(url)
        return payload()
    key="never_publish_twelve_key"
    out=tmp_path/"repo"/"data"/"private"/"twelve1"
    conf=dict(symbol="FSLR",venue="XNAS",as_of=TODAY,output=out,
              repo_root=tmp_path/"repo",api_key=key,
              live_confirm=True,terms_confirm=True,retrieved_at_utc=NOW,
              transport=transport)
    meta=td.run_pilot(**conf)
    assert len(urls)==1
    assert meta["research_status"]=="DIAGNOSTIC_ONLY_NOT_RANKABLE_NOT_TRADE_READY"
    assert meta["actual_adjustment_independently_verified"] is False
    assert len(meta["source_raw_sha256"])==64
    raw=(out/"TWELVE_PILOT_METADATA.json").read_text()
    normalized=(out/"TWELVE_SPLIT_REQUESTED_UNVERIFIED.csv").read_text()
    assert key not in raw+normalized
    assert "apikey=" not in raw
    assert normalized.startswith("date,close,volume\n")
    with pytest.raises(ValueError,match="overwrite"):
        td.run_pilot(**conf)
    assert len(urls)==1


def test_optin_output_privacy_asof_gates_before_network(tmp_path):
    def forbid(url):
        raise AssertionError("Network must not be called")
    kwargs=dict(symbol="FSLR",venue="XNAS",as_of=TODAY,
                output=tmp_path/"repo"/"reports"/"public",
                repo_root=tmp_path/"repo",api_key="test",
                retrieved_at_utc=NOW,transport=forbid)
    with pytest.raises(ValueError,match="confirmation"):
        td.run_pilot(**kwargs)
    kwargs.update(live_confirm=True,terms_confirm=True)
    with pytest.raises(ValueError,match="data/private"):
        td.run_pilot(**kwargs)
    kwargs["output"]=tmp_path/"repo"/"data"/"private"/"pilot"
    kwargs["as_of"]=date(2026,11,4)
    with pytest.raises(ValueError,match="UTC"):
        td.run_pilot(**kwargs)


def test_cli_never_queries_without_dual_confirmation(tmp_path,monkeypatch):
    monkeypatch.delenv("TWELVE_DATA_API_KEY",raising=False)
    args=["twelve-pilot","--symbol","FSLR","--venue","XNAS",
          "--output",str(tmp_path/"private")]
    with pytest.raises(SystemExit) as ex:
        main(args)
    assert ex.value.code==2
