"""R-006 EODHD catalog request: synthetic response, zero live calls."""
import json

import pytest

from investresearch.research_eodhd_catalog_collect import collect_catalog


class Reply:
    def __init__(self, url, payload):
        self.url, self.payload = url, payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.url
    def read(self, size):
        return self.payload[:size]


class Fake:
    def __init__(self, payload):
        self.payload, self.urls = payload, []
    def open(self, req, timeout):
        self.urls.append(req.full_url)
        assert timeout == 18
        return Reply(req.full_url, self.payload)


def market():
    return json.dumps([
        {"Code":"SYN","Name":"Invented","Country":"DE","Exchange":"XETRA",
         "Currency":"EUR","Type":"Common Stock","Isin":"US0378331005"},
        {"Code":"NA","Name":"Invented","Country":"IE","Exchange":"XETRA",
         "Currency":"EUR","Type":"ETF","Isin":None},
    ]).encode()


def test_one_catalog_call_stores_private_json_and_source_hash(tmp_path):
    obj=Fake(market())
    audit=collect_catalog(
        output=tmp_path/"private",repo_root=tmp_path/"public",
        api_token="SYNTHETIC_TEST_KEY_NEVER_SEND",
        personal_rights_ack=True,opener=obj)
    assert len(obj.urls)==1
    assert "SYNTHETIC_TEST_KEY_NEVER_SEND" in obj.urls[0]
    assert audit["provider_records"]==2
    assert audit["usable_isin_records"]==1
    assert audit["price_histories"]==0
    assert audit["trade_ready"] is False
    meta=json.loads((tmp_path/"private/EODHD_XETRA_SOURCE.json").read_text())
    assert "SYNTHETIC_TEST_KEY_NEVER_SEND" not in json.dumps(meta)
    assert meta["source_url"]=="https://eodhd.com/api/exchange-symbol-list/XETRA"
    with pytest.raises(ValueError,match="overwriting"):
        collect_catalog(output=tmp_path/"private",repo_root=tmp_path/"public",
            api_token="TEST", personal_rights_ack=True,opener=obj)


@pytest.mark.parametrize("change",["terms","demo","invalid_key","path"])
def test_no_catalog_request_without_authorized_scoped_inputs(tmp_path,change):
    fake=Fake(market())
    opts=dict(
        output=tmp_path/"public"/"reports",repo_root=tmp_path/"public",
        api_token="SYNTHETIC_TEST_KEY",personal_rights_ack=True,opener=fake)
    if change=="terms":opts["personal_rights_ack"]=False
    if change=="demo":opts["api_token"]="demo"
    if change=="invalid_key":opts["api_token"]=None
    if change=="path":pass
    with pytest.raises(ValueError):
        collect_catalog(**opts)
    assert not fake.urls
    assert not opts["output"].exists()


def test_vendor_rate_error_never_writes_raw(tmp_path):
    fake=Fake(b'{"status":"API limit"}')
    with pytest.raises(ValueError,match="bounded array"):
        collect_catalog(output=tmp_path/"eodhd",repo_root=tmp_path/"repo",
            api_token="SYNTHETIC_TEST_KEY",personal_rights_ack=True,opener=fake)
    assert len(fake.urls)==1
    assert not (tmp_path/"eodhd").exists()
