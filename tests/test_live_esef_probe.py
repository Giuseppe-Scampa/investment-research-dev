"""No-network validation of the optional official ESEF audit runner."""
from __future__ import annotations

import io
import zipfile
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('smoke_edison_esef', ROOT/'tools/smoke_edison_esef.py')
probe = module_from_spec(spec)
spec.loader.exec_module(probe)


def sample_esef(lei=probe.EDISON_LEI):
    content = f'''<html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
        xmlns:xbrli="http://www.xbrl.org/2003/instance"
        xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
        xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
        xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full">
    <head><title>Synthetic – not an issuer filing</title></head><body>
      <ix:header><ix:resources>
      <xbrli:context id="fy"><xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">{lei}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="EUR"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
      </ix:resources></ix:header>
      <ix:nonFraction name="ifrs-full:Revenue" contextRef="fy" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">17,739</ix:nonFraction>
      <ix:nonFraction name="ifrs-full:ProfitLoss" contextRef="fy" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">270</ix:nonFraction>
    </body></html>'''.encode()
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('package/reports/'+probe.EDISON_SUFFIX,content)
    return result.getvalue()


def test_probe_checks_pdf_references_but_never_certifies_or_ranks():
    r=probe.verify_official_package(sample_esef(),date(2026,11,2))
    assert r['candidate_count']==2
    assert r['pdf_reference_numeric_matches']==2
    assert r['accounting_facts_verified']==0
    assert r['market_ranking_count']==0
    assert r['status']=='LIVE_ESEF_CANDIDATES_UNVERIFIED_NOT_RANKED'
    assert not any('path' in k for k in r)


def test_probe_rejects_issuer_lei_mismatch():
    with pytest.raises(ValueError, match='LEI'):
        probe.verify_official_package(sample_esef(lei='12345678901234567890'),date(2026,11,2))


def test_probe_rejects_period_before_publication():
    with pytest.raises(ValueError, match='predate'):
        probe.verify_official_package(sample_esef(),date(2026,1,2))


def test_probe_refuses_unexpected_member_name():
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('package/reports/different-2025.xhtml',b'fake')
    with pytest.raises(ValueError,match='expected one consolidated XHTML member'):
        probe.verify_official_package(output.getvalue(),date(2026,11,2))


def test_probe_no_candidates_is_incomplete_even_when_zip_download_succeeded(monkeypatch, capsys):
    # The optional CI job must not label a parseable, zero-coverage ZIP a success.
    payload = io.BytesIO()
    xml = b'<html xmlns="http://www.w3.org/1999/xhtml"><head/><body/></html>'
    with zipfile.ZipFile(payload, 'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('reports/'+probe.EDISON_SUFFIX, xml)
    monkeypatch.setattr(probe, 'fetch_official_zip', lambda: payload.getvalue())
    # The real LEI field is not available in this empty XHTML, so a strictly
    # validated run should fail loudly, rather than pretending the sample works.
    assert probe.main() == 1
    assert 'NOT VALIDATED' in capsys.readouterr().err


def test_probe_reports_parseable_but_zero_coverage_as_incomplete(monkeypatch, capsys):
    raw = sample_esef()
    xml = raw
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entry = z.namelist()[0]
        xml = z.read(entry).replace(b'contextRef="fy"', b'contextRef="missing"')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(entry, xml)
    monkeypatch.setattr(probe, 'fetch_official_zip', lambda: out.getvalue())
    assert probe.main() == 2
    outlog = capsys.readouterr()
    assert 'INCOMPLETE: zero extractable candidates' in outlog.err
    assert '"candidate_count": 0' in outlog.out
