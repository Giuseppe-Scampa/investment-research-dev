"""Offline regression tests for the real-source Prysmian compatibility probe."""
from __future__ import annotations

import io
import zipfile
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('smoke_prysmian_esef',ROOT/'tools/smoke_prysmian_esef.py')
probe = module_from_spec(spec)
spec.loader.exec_module(probe)


def synthetic_package(*, lei=probe.ISSUER_LEI, value='19,650', concept='Revenue',
                      with_profit=True, filename=None):
    """Fixture invented here: no official issuer bytes are checked into Git."""
    facts = f'<ix:nonFraction name="ifrs-full:{concept}" contextRef="fy" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">{value}</ix:nonFraction>'
    if with_profit:
        facts += '<ix:nonFraction name="ifrs-full:ProfitLoss" contextRef="fy" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">1,270</ix:nonFraction>'
    xml = f'''<html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
        xmlns:xbrli="http://www.xbrl.org/2003/instance"
        xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
        xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
        xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full">
    <head/><body>
    <ix:header><ix:resources>
    <xbrli:context id="fy"><xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">{lei}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:unit id="eur"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
    </ix:resources></ix:header>
    {facts.replace('unitRef="EUR"', 'unitRef="eur"')}
    </body></html>'''.encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(filename or ('pkg/reports/'+probe.EXPECTED_REPORT_NAME), xml)
    return output.getvalue()


def test_offline_probe_two_supported_facts_still_unverified():
    report = probe.verify_official_package(synthetic_package(),date(2026,11,2))
    assert report['candidate_count'] == 2
    assert report['numeric_reference_matches'] == 2
    assert report['accounting_facts_verified'] == report['market_ranking_count'] == 0
    assert report['mode'].endswith('NOT_AUDITED')
    assert len(report['candidates']) == 2
    assert probe.validate_compatibility(report)[0] is True


def test_issuer_lei_mismatch_rejected():
    with pytest.raises(ValueError,match='LEI'):
        probe.verify_official_package(synthetic_package(lei='12345678901234567890'),date(2026,11,2))


def test_pit_and_exact_member_guards():
    with pytest.raises(ValueError,match='published'):
        probe.verify_official_package(synthetic_package(),date(2026,1,1))
    with pytest.raises(ValueError,match='exactly one'):
        probe.verify_official_package(synthetic_package(filename='pkg/reports/not-official.xhtml'),date(2026,11,2))


def test_missing_reference_match_fails_closed_without_guessing():
    result=probe.verify_official_package(synthetic_package(value='12,345',with_profit=False),date(2026,11,2))
    assert result['candidate_count']==1
    assert result['numeric_reference_matches']==0
    assert probe.validate_compatibility(result)==(False,'NO_2025_INVESTOR_REFERENCE_NUMERIC_MATCH')


def test_zero_ifrs_candidates_fails_even_if_valid_xhtml():
    result=probe.verify_official_package(synthetic_package(concept='SomeOtherConcept',with_profit=False),date(2026,11,2))
    assert result['candidate_count']==0
    assert probe.validate_compatibility(result)[0] is False


def test_no_network_on_import_or_unit_tests(monkeypatch):
    def forbidden():
        raise RuntimeError('Not authorized: this test must stay offline')
    monkeypatch.setattr(probe,'fetch_official_zip',forbidden)
    assert probe.main() == 1
