"""R-006 SEC/Xetra catalog to priced-screened coverage: ALL source fixtures invented."""
from __future__ import annotations
import hashlib
import json
import runpy

import pytest

from investresearch.cli import ROOT
from investresearch.research_discovery_coverage import build_discovery,write_discovery
from investresearch.research_screen import screen
from investresearch.research_sources import SEC_TICKERS_URL


def make_external(tmp_path):
    generate=runpy.run_path(str(ROOT/"tools/generate_crossrepo_external_fixture.py"))["generate"]
    return screen(generate(tmp_path/"synthetic_fixture_discovery"))


def sources(tmp_path):
    xetra=runpy.run_path(str(ROOT/"tests/test_eodhd_xetra_crosswalk.py"))["xetra"]
    raw,meta=xetra()
    x=tmp_path/"xetra.csv";x.write_bytes(raw)
    xm=tmp_path/"xetra_meta.json";xm.write_text(json.dumps(meta))
    sec=json.dumps({
        "fields":["cik","name","ticker","exchange"],
        "data":[[1,"Synthetic company","FAKE","Nasdaq"],
                [2,"Another invented company","ALPHA","NYSE"],
                [3,"Nonmapped","NOEX","OTC"]]
    }).encode()
    y=tmp_path/"sec.json";y.write_bytes(sec)
    ym=tmp_path/"sec_meta.json";ym.write_text(json.dumps({
        "provider":"SEC_TICKERS","source_url":SEC_TICKERS_URL,
        "sha256":hashlib.sha256(sec).hexdigest(),
        "retrieved_at_utc":"2026-11-05T18:00:00Z"}))
    return (x,xm),(y,ym)


def test_offline_reference_catalogs_do_not_masquerade_as_prices_or_global_diversity(tmp_path):
    s=make_external(tmp_path)
    xetra,sec=sources(tmp_path)
    report=build_discovery(s,xetra=xetra,sec=sec,repo_root=ROOT)
    assert report["source_screened_universe_count"]==2
    assert report["source_ranked_count"]==2
    assert report["reference_catalog_count"]==2
    assert report["reference_catalogs"]["XETRA_T7"]["catalog_count"]==4
    assert report["reference_catalogs"]["SEC_US_EXCHANGES"]["supported_venue_listings"]==2
    assert report["reference_catalogs"]["SEC_US_EXCHANGES"]["screening_isin_matches_proven"]==0
    assert report["SEC_ticker_only_not_ISIN_confirmed"] is True
    assert report["exact_verified_xetra_reference_matches"]==0
    assert not report["global_representative_universe_certified"]
    assert not report["trade_ready"]
    write_discovery(report,tmp_path/"report",repo_root=ROOT)
    assert json.loads((tmp_path/"report/DISCOVERY_COVERAGE.json").read_text())==report


def test_without_reference_catalog_does_not_invent_discovery_coverage():
    s=screen(ROOT/"data/research/demo")
    report=build_discovery(s)
    assert report["reference_catalog_count"]==0
    assert report["status"]=="NO_INDEPENDENT_DISCOVERY_REFERENCE_SUPPLIED"
    assert report["source_screened_universe_count"]==7


@pytest.mark.parametrize("mut",["bad_hash","future","bad_provider","bad_url"])
def test_reference_provenance_fails_closed(tmp_path,mut):
    s=make_external(tmp_path)
    xetra,sec=sources(tmp_path)
    path=sec[1]
    m=json.loads(path.read_text())
    if mut=="bad_hash":m["sha256"]="0"*64
    elif mut=="future":m["retrieved_at_utc"]="2026-11-07T10:00:00Z"
    elif mut=="bad_provider":m["provider"]="YAHOO_NO_RIGHTS"
    elif mut=="bad_url":m["source_url"]="https://invalid.example.com/api"
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        build_discovery(s,xetra=xetra,sec=sec,repo_root=ROOT)


def test_external_catalog_is_refused_for_synthetic_dataset(tmp_path):
    s=screen(ROOT/"data/research/demo")
    xetra,_=sources(tmp_path)
    with pytest.raises(ValueError,match="cannot certify synthetic"):
        build_discovery(s,xetra=xetra,repo_root=ROOT)
