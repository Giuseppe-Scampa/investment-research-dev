"""Independent tests for narrow, fail-closed inline XBRL numeric evidence extraction."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from datetime import date
import pytest

from investresearch.research_eu_filings import MODE, audit_eu_reports, write_eu_report
from investresearch.research_ixbrl import extract_ixbrl_ifrs_candidates
from investresearch.research_cli import main

HEAD = '''<html xmlns="http://www.w3.org/1999/xhtml"
  xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
  xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
  xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full"
  xmlns:issuer="https://issuer.example.test/taxonomy/extension">
<head><title>Entirely synthetic IFRS fixture</title></head>
<body><ix:header><ix:resources>
<xbrli:context id="FY25"><xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">12345678901234567890</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="FY24"><xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">12345678901234567890</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="FY25_DIM"><xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">12345678901234567890</xbrli:identifier><xbrli:segment><xbrli:explicitMember>segment</xbrli:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:unit id="EUR"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
<xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:resources></ix:header>
'''
END = '</body></html>'

def fact(name='ifrs-full:Revenue',value='1,200.5',context='FY25',unit='EUR',scale='6',fmt='ixt:num-dot-decimal', sign=''):
    return (f'<ix:nonFraction name="{name}" contextRef="{context}" unitRef="{unit}"'
            f' scale="{scale}" format="{fmt}"{f" sign={chr(34)}{sign}{chr(34)}" if sign else ""}>'
            f'{value}</ix:nonFraction>')

def xhtml(*numbers):
    return (HEAD + ''.join(numbers) + END).encode()


def fixture(tmp_path: Path, data: bytes, fmt='ESEF_XHTML',member=None):
    root=tmp_path/'doc';root.mkdir()
    filename='annual.zip' if fmt=='ESEF_ZIP' else 'annual.xhtml'
    (root/filename).write_bytes(data)
    doc={'id':'SYNTH_EU_FY25','issuer_name':'Synthetic European public issuer',
         'format':fmt,'source_type':'ISSUER_INVESTOR_RELATIONS',
         'relative_path':filename,'sha256':hashlib.sha256(data).hexdigest(),
         'source_url':'https://issuer.example.test/annual-filing',
         'published_date':'2026-03-20','fiscal_year_end':'2025-12-31',
         'retrieved_at_utc':'2026-10-01T09:00:00+00:00'}
    if member:doc['xhtml_member']=member
    return root,{'mode':MODE,'as_of':'2026-11-02','documents':[doc]}


def test_ifrs_revenue_and_profit_transform_scale_sign_and_provisional_status(tmp_path):
    xml=xhtml(fact(),fact('ifrs-full:ProfitLoss','400,25',fmt='ixt:num-comma-decimal',scale='3',sign='-'))
    result=extract_ixbrl_ifrs_candidates(xml,date(2025,12,31))
    assert result['candidate_count']==2
    items={r['metric']:r for r in result['facts']}
    assert items['REVENUE']['value_eur']=='1200500000.0'
    assert items['PROFIT_LOSS']['value_eur']=='-400250.00'
    assert items['REVENUE']['period_end']=='2025-12-31'
    assert result['verified_fundamental_count']==0
    assert 'REVIEW' in result['status']
    root,spec=fixture(tmp_path,xml)
    inventory=audit_eu_reports(spec,root,extract_ifrs=True)
    assert inventory['ixbrl_candidate_count']==2
    assert inventory['accounting_facts_verified']==0
    assert inventory['market_ranking_count']==0
    assert str(root) not in json.dumps(inventory)
    out=write_eu_report(inventory,tmp_path/'out')
    assert (out/'EU_REPORT_COVERAGE.json').is_file()
    assert '1200500000' in (out/'EU_REPORT_COVERAGE.json').read_text()
    assert (out/'EU_REPORT_COVERAGE.csv').exists()
    assert 'Verified numerical fundamentals:** 0' in (out/'EU_REPORT_COVERAGE.md').read_text()


def test_default_inventory_never_extracts_facts(tmp_path):
    root,spec=fixture(tmp_path,xhtml(fact()))
    report=audit_eu_reports(spec,root)
    assert report['ixbrl_candidate_count']==0
    assert 'ixbrl' not in report['results'][0]
    (root/'spec.json').write_text(json.dumps(spec))
    main(['eu-filings','--spec',str(root/'spec.json'),'--extract-ifrs',
          '--output',str(tmp_path/'cli-out')])
    assert json.loads((tmp_path/'cli-out/EU_REPORT_COVERAGE.json').read_text())['ixbrl_candidate_count']==1


def test_dont_mix_prior_periods_currencies_dimensions_or_extension_tags():
    xml=xhtml(fact(),fact(value='900',context='FY24'),fact(value='800',unit='USD'),
              fact(value='200',context='FY25_DIM'),fact('issuer:Revenue','99999'))
    d=extract_ixbrl_ifrs_candidates(xml,date(2025,12,31))
    assert d['candidate_count']==1
    assert d['rejected_fact_reasons']['NO_CURRENT_UNDIMENSIONED_ANNUAL_CONTEXT']==2
    assert d['rejected_fact_reasons']['UNSUPPORTED_OR_NON_EUR_UNIT']==1
    assert d['conflicting_concepts']==[]


def test_conflicting_duplicate_facts_are_not_silently_resolved():
    result=extract_ixbrl_ifrs_candidates(xhtml(fact(value='100'),fact(value='200')),date(2025,12,31))
    assert result['candidate_count']==2
    assert result['conflicting_concepts']==['REVENUE:Revenue']
    assert result['verified_fundamental_count']==0


@pytest.mark.parametrize('invalid',[
    fact(value='1.234',fmt='ixt:unknown-format'),
    fact(value='1.234.5'),
    fact(value='-',fmt='ixt:num-dot-decimal'),
    fact(value='1,99,9',fmt='ixt:num-comma-decimal'),
    fact(value='1,123',fmt='ixt:num-dot-decimal',scale='100'),
    fact(value='1,234',fmt='ixt:num-dot-decimal',scale='0',sign='INVALID'),
])
def test_unsupported_numeric_facts_are_not_assumed_to_be_zero(invalid):
    r=extract_ixbrl_ifrs_candidates(xhtml(invalid),date(2025,12,31))
    assert r['candidate_count']==0
    assert r['rejected_fact_reasons']['NUMERIC_TRANSFORMATION_REQUIRES_REVIEW']==1


def test_xhtml_entity_expansion_is_rejected_without_extraction():
    payload=(b'<!DOCTYPE lolz [<!ENTITY a "lol"><!ENTITY b "&a;&a;&a;">]>'
             +xhtml(fact()).replace(b'1,200.5',b'&b;'))
    with pytest.raises((ValueError,Exception),match='EntitiesForbidden|entity|Unsafe|DTD'):
        extract_ixbrl_ifrs_candidates(payload,date(2025,12,31))


def test_xhtml_bad_prefix_rebinding_refused():
    xml=xhtml(fact()).replace(b'</body>',b'<div xmlns:ifrs-full="https://attacker.example.test/fake"/></body>')
    with pytest.raises(ValueError,match='namespace prefix rebound'):
        extract_ixbrl_ifrs_candidates(xml,date(2025,12,31))


def pack(members):
    handle=io.BytesIO()
    with zipfile.ZipFile(handle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path,body in members.items():z.writestr(path,body)
    return handle.getvalue()


def test_zip_extracts_only_selected_member_and_refuses_ambiguous_xhtml(tmp_path):
    xml=xhtml(fact())
    archive=pack({'issuer/annual.xhtml':xml,'issuer/notes.xhtml':xhtml()})
    root,spec=fixture(tmp_path,archive,fmt='ESEF_ZIP')
    with pytest.raises(ValueError,match='Multiple XHTML members'):
        audit_eu_reports(spec,root,extract_ifrs=True)
    spec['documents'][0]['xhtml_member']='issuer/annual.xhtml'
    assert audit_eu_reports(spec,root,extract_ifrs=True)['ixbrl_candidate_count']==1
    spec['documents'][0]['xhtml_member']='../annual.xhtml'
    with pytest.raises(ValueError,match='not present'):
        audit_eu_reports(spec,root,extract_ifrs=True)


def test_zip_actual_inflation_limit_not_just_declared_central_directory(tmp_path,monkeypatch):
    from investresearch import research_ixbrl
    monkeypatch.setattr(research_ixbrl,'MAX_XHTML_BYTES',90)
    zipped=pack({'report.xhtml':xhtml(fact())})
    root,spec=fixture(tmp_path,zipped,fmt='ESEF_ZIP')
    with pytest.raises(ValueError,match='exceeds bounded'):
        audit_eu_reports(spec,root,extract_ifrs=True)


def test_pdf_extract_opt_in_remains_manual_only(tmp_path):
    root,spec=fixture(tmp_path,b'%PDF-1.7\nsynthetic',fmt='ANNUAL_PDF')
    # Change relative filename/extension so PDF format is otherwise valid.
    report=audit_eu_reports(spec,root,extract_ifrs=True)
    assert report['ixbrl_candidate_count']==0
    assert report['results'][0]['ixbrl']['status']=='PDF_REQUIRES_MANUAL_ACCOUNTING_EXTRACTION'


def test_review_export_is_opt_in_and_has_unreviewed_rows(tmp_path):
    root,spec=fixture(tmp_path,xhtml(fact()))
    out=tmp_path/'review'
    write_eu_report(audit_eu_reports(spec,root),out)
    assert not (out/'EU_IFRS_CANDIDATES_REVIEW.csv').exists()
    write_eu_report(audit_eu_reports(spec,root,extract_ifrs=True),out)
    import csv
    with (out/'EU_IFRS_CANDIDATES_REVIEW.csv').open() as stream:
        data=list(csv.DictReader(stream))
    assert len(data)==1
    assert data[0]['metric']=='REVENUE'
    assert data[0]['human_review_status']=='UNREVIEWED_NOT_CERTIFIED'
    assert data[0]['accounting_scope_to_check']=='UNVERIFIED'
    assert data[0]['document_sha256']==spec['documents'][0]['sha256']
    assert str(root) not in (out/'EU_IFRS_CANDIDATES_REVIEW.csv').read_text()


def test_optional_lei_must_match_reporting_entity_in_xhtml(tmp_path):
    root,spec=fixture(tmp_path,xhtml(fact()))
    doc=spec['documents'][0]
    doc['lei']='12345678901234567890'
    assert audit_eu_reports(spec,root,extract_ifrs=True)['ixbrl_candidate_count']==1
    doc['lei']='09876543210987654321'
    with pytest.raises(ValueError,match='does not match'):
        audit_eu_reports(spec,root,extract_ifrs=True)
    doc['lei']='INVALID'
    with pytest.raises(ValueError,match='20-character'):
        audit_eu_reports(spec,root,extract_ifrs=True)


def test_duplicate_zip_members_are_rejected_before_extracting(tmp_path):
    archive=io.BytesIO()
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('report.xhtml',xhtml(fact()))
            z.writestr('report.xhtml',xhtml(fact()))
    root,spec=fixture(tmp_path,archive.getvalue(),fmt='ESEF_ZIP')
    with pytest.raises(ValueError,match='Duplicate ESEF ZIP member'):
        audit_eu_reports(spec,root,extract_ifrs=True)
