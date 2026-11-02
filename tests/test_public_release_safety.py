"""Guardrails for the deliberately synthetic public export."""
import json
from pathlib import Path
from investresearch.cli import ROOT


def test_synthetic_settings_and_case_do_not_match_old_private_data():
    settings=json.loads((ROOT/'config/settings.json').read_text())
    demo=json.loads((ROOT/'data/fixtures/investment_case_example.json').read_text())
    assert settings['broker'].startswith('Demo Broker')
    assert settings['capital_eur']==20000
    assert settings['loss_carryforward_eur']==2500
    assert demo['fixture_kind']=='SYNTHETIC_DEMONSTRATION_NOT_PERSONAL_HOLDINGS'
    assert demo['investment_budget_eur']=='20000'
    assert all(w['account_id'].startswith('SYNTHETIC_') for w in demo['tax_wallets'])


def test_no_billable_ai_runtime_or_workflow():
    assert not (ROOT/'src/investresearch/research_runner.py').exists()
    assert not (ROOT/'research/deep_research_prompt.md').exists()
    workflow=(ROOT/'.github/workflows/research.yml').read_text()
    assert 'OPENAI_API_KEY' not in workflow
    assert 'gpt-5.5' not in workflow
    project=(ROOT/'pyproject.toml').read_text()
    assert 'openai>=' not in project.lower()
