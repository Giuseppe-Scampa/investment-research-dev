from datetime import date
import json
from pathlib import Path
import pytest
from investresearch.quality import valid_isin,read_strict_csv,audit
from investresearch.dashboard import html_report
from investresearch.cli import ROOT

def test_valid_isin_checksums():
    assert valid_isin('FR0000120628')
    assert valid_isin('IT0004176001')
    assert not valid_isin('FR0000120629')
    assert not valid_isin('foo')

def test_strict_duplicate_ids(tmp_path):
    p=tmp_path/'bad.csv';p.write_text('id,price\nA,1\nA,2\n')
    with pytest.raises(ValueError,match='duplicate'):read_strict_csv(p)

def test_audit_blocks_stale_and_future():
    instruments=[{'id':'AXA','isin':'FR0000120628','oil_exposure':'none','fiscal_status':'eligible','exchange':'Euronext Paris'}]
    q=[{'id':'AXA','price':'42.60','market_date':'2026-10-30','source_url':'https://example.org'}]
    stale=audit(instruments,q,date(2026,11,10))
    assert any(s.gate=='freshness' and s.severity=='INCOMPLETE' for s in stale)
    future=audit(instruments,q,date(2026,10,29))
    assert any(s.gate=='look_ahead' and s.severity=='BLOCKED' for s in future)

def test_audit_blocks_invalid_values():
    instruments=[{'id':'AXA','isin':'FR0000120628','oil_exposure':'none','fiscal_status':'eligible','exchange':'Euronext Paris'}]
    q=[{'id':'AXA','price':'NaN','market_date':'2026-10-30','source_url':'http://unsafe'}]
    assert any(s.gate=='quote' and s.severity=='BLOCKED' for s in audit(instruments,q,date(2026,11,1)))

def test_dashboard_generated_and_escaped(tmp_path):
    (tmp_path/'portfolio_scenarios.csv').write_text('portfolio,scenario,invested_eur,cash_eur,net_pnl_excluding_market_spread_eur\nA,bear,100,0,-10\n')
    (tmp_path/'DEEP_RESEARCH.md').write_text('# Research <script>alert(1)</script>\n')
    (tmp_path/'research_manifest.json').write_text('{"status":"AI_RESEARCH_COMPLETED_NOT_FACT_CHECKED", "citation_count":5}')
    blockers=html_report(tmp_path)
    html=(tmp_path/'dashboard.html').read_text()
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html
    assert blockers==0  # 2026-11-01 has incomplete research, no hard trading authorization
    assert (tmp_path/'quality_gates.json').exists()

def test_real_snapshots_have_unique_ids():
    inst=read_strict_csv(ROOT/'data/snapshots/instruments.csv')
    quotes=read_strict_csv(ROOT/'data/snapshots/verified_quotes.csv')
    assert len(inst)>=10
    assert all(x['id'] for x in quotes)
