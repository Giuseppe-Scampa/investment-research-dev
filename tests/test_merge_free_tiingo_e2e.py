"""Free-source multi-ISIN aggregation → official-format ECB → risk.

All prices and ECB rates in this test are invented fixtures, NOT actual
market observations or acceptable standalone source entitlements.
"""
from __future__ import annotations

import copy
import hashlib
import json
import runpy
from pathlib import Path

import pytest

from investresearch.cli import ROOT
from investresearch.research_intake_merge import combine
from investresearch.research_fx_bundle import bind_ecb_fx
from investresearch.research_bundle import build_bundle
from investresearch.research_screen import screen
from investresearch.tactical_research import build_tactical
from investresearch.research_risk import analyze_risk
from investresearch.tax_engine import FiscalRegistry


def setup(tmp_path):
    generator=runpy.run_path(
        str(ROOT/"tools/generate_crossrepo_external_fixture.py"))["generate"]
    rawdir=tmp_path/"synthetic_fixture_free_merge"
    generator(rawdir)
    original=json.loads((rawdir/"SYNTHETIC_TEST_ONLY_SPEC.json").read_text())
    inputs=[]
    for n,asset in enumerate(original["assets"]):
        single_asset=copy.deepcopy(asset)
        # Actual personal collector uses exactly ISIN as bundle asset id.
        single_asset["id"]=single_asset["isin"]
        spec={"mode":original["mode"],"as_of":original["as_of"],
              "assets":[single_asset]}
        p=rawdir/f"TIINGO_PERSONAL_SOURCE_{n}.json"
        p.write_text(json.dumps(spec))
        inputs.append(p)
    meta=rawdir/"ECB_META.json"
    meta.write_text(json.dumps(original["fx_source"]))
    return rawdir,inputs,meta


def test_n_sources_to_real_screen_tactical_risk_codepath(tmp_path):
    rawdir,inputs,fxmeta=setup(tmp_path)
    merged=rawdir/"MERGED_TIINGO.json"
    audit=combine(source_specs=inputs,output=merged,repo_root=ROOT)
    assert audit["source_assets"]==2 and not audit["fx_bound"]
    assert audit["by_type"]=={"EQUITY":2}
    assert audit["actual_prices_quality_tested"] is False
    combined=rawdir/"WITH_ECB.json"
    rate=bind_ecb_fx(spec_path=merged,fx_meta_path=fxmeta,
                     output=combined,repo_root=ROOT)
    assert rate["usd_assets"]==2
    bundle=rawdir/"COMBINED_BUNDLE"
    metadata=build_bundle(json.loads(combined.read_text()),bundle)
    assert len(metadata["assets"])==2
    screened=screen(bundle)
    assert screened["ranked_count"]==2
    fiscal=FiscalRegistry.load(ROOT/"config/fiscal/rules_2026.json")
    tactical=build_tactical(screened,fiscal_registry=fiscal)
    assert len(tactical["research_priorities_by_type"])==2
    risks=analyze_risk(bundle,screened,tactical)
    assert risks["pairs_count"]==1
    assert risks["trade_ready"] is False
    assert tactical["trade_ready"] is False


@pytest.mark.parametrize("mutation,expected", [
    ("repeated_spec","Repeated"),
    ("duplicate_isin","Duplicate"),
    ("wrong_asof","as-of"),
    ("missing_hash","SHA"),
    ("wrong_rights","rights"),
    ("wrong_identity","ISIN/venue"),
    ("eodhd","No EODHD"),
    ("bad_url","URL"),
])
def test_local_multi_source_merge_refuses_hidden_provider_and_conflicts(
        tmp_path,mutation,expected):
    rawdir,paths,_=setup(tmp_path)
    first=json.loads(paths[0].read_text())
    second=json.loads(paths[1].read_text())
    if mutation=="repeated_spec":
        paths[1]=paths[0]
    elif mutation=="duplicate_isin":
        second["assets"][0]["isin"]=first["assets"][0]["isin"]
        second["assets"][0]["id"]=first["assets"][0]["id"]
        second["assets"][0]["prices_source"]["isin"]=first["assets"][0]["isin"]
    elif mutation=="wrong_asof":
        second["as_of"]="2026-11-04"
    elif mutation=="missing_hash":
        second["assets"][0]["prices_source"]["sha256"]="0"*64
    elif mutation=="wrong_rights":
        second["assets"][0]["prices_source"]["usage_attestation"]="NOT_ACCEPTED"
    elif mutation=="wrong_identity":
        second["assets"][0]["prices_source"]["isin"]="GB00B15KXQ89"
    elif mutation=="eodhd":
        second["assets"][0]["prices_source"]["provider"]="EODHD_EOD_PERSONAL_RESEARCH"
    elif mutation=="bad_url":
        second["assets"][0]["prices_source"]["source_url"]="https://untrusted.invalid/a"
    paths[1].write_text(json.dumps(second))
    with pytest.raises(ValueError,match=expected):
        combine(source_specs=paths,output=rawdir/"REJECTED.json",repo_root=ROOT)
    assert not (rawdir/"REJECTED.json").exists()


def test_merge_rejects_reusing_output_and_single_source(tmp_path):
    root,paths,_=setup(tmp_path)
    with pytest.raises(ValueError,match="between 2"):
        combine(source_specs=paths[:1],output=root/"SINGLE.json",repo_root=ROOT)
    output=root/"merged.json"
    combine(source_specs=paths,output=output,repo_root=ROOT)
    with pytest.raises(ValueError,match="NEW"):
        combine(source_specs=paths,output=output,repo_root=ROOT)
