"""Independent offline tests for EU document evidence and manual market-data rights gates."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from investresearch.research_bundle import EXTERNAL, MANUAL_OHLCV, build_bundle
from investresearch.research_cli import main
from investresearch.research_eu_filings import (
    MODE, audit_eu_reports, write_eu_report,
)
from investresearch.research_screen import screen
from investresearch.research_sources import sha256_bytes
from investresearch.demo_dataset import _days


def _doc(tmp_path, name='report.xhtml', data=b'<html xmlns="http://www.w3.org/1999/xhtml"><body>Sample</body></html>', **kw):
    root=tmp_path/'local_docs';root.mkdir(exist_ok=True)
    (root/name).write_bytes(data)
    entry={
        'id':'ISSUER_A_FY25','issuer_name':'Issuer Alpha (synthetic)',
        'isin':'','format':'ESEF_XHTML','source_type':'ISSUER_INVESTOR_RELATIONS',
        'relative_path':name, 'sha256':hashlib.sha256(data).hexdigest(),
        'source_url':'https://issuer.example.test/investors/annual-2025.xhtml',
        'published_date':'2026-03-31','fiscal_year_end':'2025-12-31',
        'retrieved_at_utc':'2026-10-31T09:00:00+00:00',
    }
    entry.update(kw)
    return root, {'mode':MODE,'as_of':'2026-11-02','documents':[entry]}


def test_european_evidence_inventory_is_not_financial_data(tmp_path):
    root,spec=_doc(tmp_path)
    report=audit_eu_reports(spec,root)
    assert report['document_count']==1
    assert report['esef_documents']==1
    assert report['accounting_facts_verified']==report['market_ranking_count']==0
    assert report['results'][0]['market_score'] is None
    assert report['results'][0]['status']=='DOCUMENT_HASH_FORMAT_VALID_SOURCE_AND_ACCOUNTING_NOT_VERIFIED'
    write_eu_report(report,tmp_path/'generated')
    for name in ('EU_REPORT_COVERAGE.json','EU_REPORT_COVERAGE.csv','EU_REPORT_COVERAGE.md'):
        contents=(tmp_path/'generated'/name).read_text()
        assert 'local_docs' not in contents
        assert 'Sample</body>' not in contents
        assert 'ISSUER_A_FY25' in contents or name.endswith('.md')
    (root/'spec.json').write_text(json.dumps(spec))
    main(['eu-filings','--spec',str(root/'spec.json'),'--output',str(tmp_path/'cli-output')])
    assert (tmp_path/'cli-output/EU_REPORT_COVERAGE.json').is_file()


@pytest.mark.parametrize('field,value,match',[
    ('published_date','2026-11-03','Future'),
    ('retrieved_at_utc','2026-11-03T08:00:00Z','Future'),
    ('fiscal_year_end','2027-01-01','Future'),
    ('source_url','http://issuer.example.test/file.xhtml','HTTPS'),
    ('source_url','https://localhost/file.xhtml','HTTPS'),
    ('source_url','https://user:pass@issuer.example.test/file.xhtml','HTTPS'),
    ('format','UNSUPPORTED','Unsupported'),
    ('source_type','ANY_WEBSITE','Unrecognized'),
    ('sha256','0'*64,'checksum mismatch'),
    ('sha256','','SHA-256'),
    ('relative_path','../secret.txt','traversal'),
])
def test_eu_filing_fail_closed_on_invalid_sources_dates_and_hashes(tmp_path, field, value, match):
    root,spec=_doc(tmp_path)
    spec['documents'][0][field]=value
    with pytest.raises(ValueError,match=match):
        audit_eu_reports(spec,root)


def test_eu_filing_rejects_symlink_and_duplicate_ids(tmp_path):
    root,spec=_doc(tmp_path)
    (root/'link.xhtml').symlink_to(root/'report.xhtml')
    spec['documents'][0]['relative_path']='link.xhtml'
    with pytest.raises(ValueError,match='symlink'):
        audit_eu_reports(spec,root)
    spec['documents'][0]['relative_path']='report.xhtml'
    spec['documents'].append(dict(spec['documents'][0]))
    with pytest.raises(ValueError,match='duplicate'):
        audit_eu_reports(spec,root)


def test_eu_document_pdf_and_zip_detected_but_not_parsed_as_financials(tmp_path):
    pdf=b'%PDF-1.7\n% synthetic test document\n'
    root,spec=_doc(tmp_path,'sample.pdf',pdf,format='ANNUAL_PDF')
    assert audit_eu_reports(spec,root)['esef_documents']==0
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('issuer/report.xhtml','<html xmlns="http://www.w3.org/1999/xhtml"></html>')
    root,spec=_doc(tmp_path,'sample.zip',archive.getvalue(),format='ESEF_ZIP')
    assert audit_eu_reports(spec,root)['esef_documents']==1
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('../escape/report.xhtml','<html></html>')
    root,spec=_doc(tmp_path,'bad.zip',archive.getvalue(),format='ESEF_ZIP')
    with pytest.raises(ValueError,match='Unsafe'):
        audit_eu_reports(spec,root)


def _manual_spec(tmp_path, *, source_override=None):
    from datetime import datetime
    prices=tmp_path/'prices.csv'
    days=_days('XMIL')[-65:]
    prices.write_text('Date,Open,High,Low,Close,Volume\n'+''.join(
        f'{d},{100+i*.1:.2f},{101+i*.1:.2f},{99+i*.1:.2f},{100+i*.1:.2f},120000\n'
        for i,d in enumerate(days)))
    source={
        'provider':MANUAL_OHLCV, 'path':str(prices),
        'source_url':'https://market-data.example.test/authorized/series.csv',
        'sha256':sha256_bytes(prices.read_bytes()),
        'retrieved_at_utc':'2026-11-01T09:00:00+00:00',
        'usage_attestation':'LOCAL_RESEARCH_RIGHTS_ASSERTED_NOT_VERIFIED',
    }
    if source_override: source.update(source_override)
    spec={'mode':EXTERNAL,'as_of':'2026-11-02','assets':[
        {'id':'EXAMPLE_MANUAL','name':'Sample price instrument','asset_type':'EQUITY',
         'venue':'XMIL','currency':'EUR','sector':'Industrials','oil_exposure':'none',
         'prices_source':source}]}
    return spec,prices


def test_authorized_local_price_csv_is_importable_but_never_trade_ready(tmp_path):
    spec,_=_manual_spec(tmp_path)
    build_bundle(spec,tmp_path/'bundle')
    report=screen(tmp_path/'bundle')
    row=report['results'][0]
    assert row['price_source']==MANUAL_OHLCV
    assert row['status']=='RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY'
    assert row['market_score'] is not None and not row['trade_ready']
    assert 'LOCAL_RESEARCH_RIGHTS_ASSERTED_NOT_VERIFIED' not in str(report)  # attestation never echoed
    manifest=json.loads((tmp_path/'bundle/manifest.json').read_text())
    assert manifest['assets'][0]['prices']['usage_rights_status']=='USER_ASSERTED_LOCAL_ONLY_NEVER_VERIFIED_BY_ENGINE'
    assert 'MANUAL_CLOSE_UNADJUSTED_NOT_TOTAL_RETURN' in str(manifest)


@pytest.mark.parametrize('changes,pattern',[
    ({'usage_attestation':'YES'},'rights attestation'),
    ({'usage_attestation':None},'rights attestation'),
    ({'sha256':None},'SHA-256'),
    ({'sha256':'0'*64},'hash differs'),
    ({'source_url':'file:///etc/passwd'},'HTTPS'),
    ({'source_url':'http://example.com/price.csv'},'HTTPS'),
    ({'retrieved_at_utc':None},'timestamp'),
])
def test_local_market_price_import_rejects_insufficient_provenance(tmp_path,changes,pattern):
    spec,_=_manual_spec(tmp_path,source_override=changes)
    with pytest.raises(ValueError,match=pattern):
        build_bundle(spec,tmp_path/'bundle')


def test_untrusted_yahoo_price_source_also_requires_integrity_hash(tmp_path):
    spec,raw=_manual_spec(tmp_path)
    p=spec['assets'][0]['prices_source']
    p.update(provider='YFINANCE_EOD_UNVERIFIED',
             source_url='https://finance.yahoo.com/quote/TEST.MI/history/')
    p.pop('sha256')
    with pytest.raises(ValueError,match='SHA-256'):
        build_bundle(spec,tmp_path/'bundle')
