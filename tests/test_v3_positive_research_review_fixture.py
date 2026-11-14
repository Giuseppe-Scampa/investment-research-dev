"""Positive M4/M5 producer contract on FAKE EXTERNAL-source price histories."""
from __future__ import annotations
import json
import runpy
from pathlib import Path

import pytest

from investresearch.cli import ROOT
from investresearch.research_screen import screen
from investresearch.research_valuation import build_valuation
from investresearch.ai_provider_review import reconcile


def test_real_codepath_fictional_valuation_and_two_critic_models(tmp_path):
    generator=runpy.run_path(str(ROOT/"tools/generate_crossrepo_external_fixture.py"))["generate"]
    bundle=generator(tmp_path/"synthetic_fixture_price_data")
    producer=runpy.run_path(str(ROOT/"tools/generate_v3_review_fixtures.py"))["generate"]
    review_folder=producer(bundle=bundle,output=tmp_path/"synthetic_fixture_public_research")
    original=screen(bundle)
    valuation=json.loads((review_folder/"FAKE_ISSUER_VALUATION.json").read_text())
    report=build_valuation(original,valuation)
    assert report["source_asserted_valuations_count"]==2
    assert report["rank_or_tax_effect"] is False
    assert all(x["status"]=="SOURCE_ASSERTED_FINANCIAL_RATIOS_NOT_INDEPENDENTLY_VERIFIED"
               for x in report["items"])
    assert all(x["ratios"]["historical_ev_to_ebitda"] is not None for x in report["items"])
    ai=[json.loads((review_folder/f"FAKE_AI_ORIGINAL_{i}.json").read_text()) for i in (1,2)]
    consensus=reconcile(ai)
    assert consensus["provider_count"]==2
    assert consensus["literal_overlaps"]==1
    assert not consensus["citation_claim_support_fact_checked"]
    assert not consensus["trade_ready"]


def test_fake_original_generator_refuses_misleading_output_path(tmp_path):
    generator=runpy.run_path(str(ROOT/"tools/generate_crossrepo_external_fixture.py"))["generate"]
    bundle=generator(tmp_path/"synthetic_fixture_only")
    produce=runpy.run_path(str(ROOT/"tools/generate_v3_review_fixtures.py"))["generate"]
    with pytest.raises(ValueError,match="synthetic_fixture"):
        produce(bundle=bundle,output=tmp_path/"generic_path")
    assert not (tmp_path/"generic_path").exists()
