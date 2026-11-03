"""Independent no-network tests for the opt-in Yahoo adapter and SEC secret boundary."""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import pytest
from investresearch.demo_dataset import _days
from investresearch.research_sources import (collect, YFINANCE, yahoo_source_url,
    sha256_bytes, parse_ohlcv)
from investresearch.research_bundle import EXTERNAL, build_bundle
from investresearch.research_screen import screen


@pytest.fixture(autouse=True)
def freeze_synthetic_yahoo_snapshot_clock(monkeypatch):
    """The as-of 2026-11-02 test uses a synthetic same-day retrieval time.

    Production collection always records actual UTC; no backdated live data.
    """
    from datetime import datetime as RealDatetime, timezone
    import investresearch.research_sources as source_module

    class FrozenDatetime(RealDatetime):
        @classmethod
        def now(cls, tz=None):
            stamp = RealDatetime(2026, 11, 2, 12, tzinfo=timezone.utc)
            return stamp.astimezone(tz) if tz is not None else stamp.replace(tzinfo=None)

    monkeypatch.setattr(source_module, 'datetime', FrozenDatetime)


class Frame:
    def __init__(self, rows, columns=None):
        self.rows=rows
        self.empty=not bool(rows)
        self.columns=columns or ['Open','High','Low','Close','Volume','Dividends','Stock Splits']
    def iterrows(self):
        yield from self.rows


def sample_frame(n=65, *, split=False):
    days=_days('XMIL')[-n:]
    bars=[]
    for i,d in enumerate(days):
        p=Decimal('100') + Decimal(i)/Decimal('20')
        bars.append((datetime.fromisoformat(str(d)),{
            'Open':str(p),'High':str(p+1),'Low':str(p-1),
            'Close':str(p),'Volume':'150000',
            'Dividends':'0.20' if i==20 else '0',
            'Stock Splits':'2' if split and i==n-10 else '0'}))
    return Frame(bars)


def test_yfinance_requires_opt_in_and_safe_symbol(tmp_path):
    called=[]
    def fake(*args):
        called.append(args)
        return sample_frame()
    with pytest.raises(ValueError,match='acknowledgement'):
        collect(YFINANCE,'AAPL',tmp_path,history_loader=fake)
    with pytest.raises(ValueError,match='Invalid Yahoo symbol'):
        collect(YFINANCE,'AAPL; echo SECRET',tmp_path,acknowledge_yahoo_terms=True,history_loader=fake)
    assert not called
    assert yahoo_source_url('ENI.MI').endswith('ENI.MI/history/')
    assert '%3D' in yahoo_source_url('EURUSD=X')


def test_yfinance_cache_provenance_and_deterministic_canonical_csv(tmp_path):
    calls=[]
    def fake(symbol,start,end):
        calls.append((symbol,start,end))
        return sample_frame()
    output=collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                   as_of='2026-11-02',history_loader=fake)
    assert output['provider']==YFINANCE
    assert output['source_url']=='https://finance.yahoo.com/quote/TEST.MI/history/'
    assert output['price_basis']=='YAHOO_CLOSE_AUTO_ADJUST_FALSE_NOT_TOTAL_RETURN'
    assert output['dividend_dates'] and output['split_dates']==[]
    assert output['sha256']==sha256_bytes(Path(output['path']).read_bytes())
    assert len(parse_ohlcv(Path(output['path']).read_bytes(),date(2026,11,2)))==65
    assert calls[0][0]=='TEST.MI' and calls[0][2]==date(2026,11,3)
    assert 'apikey' not in json.dumps(output).lower()
    again=collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                  as_of='2026-11-02',history_loader=fake)
    assert again['sha256']==output['sha256']
    Path(output['path']).write_bytes(b'tamper')
    with pytest.raises(ValueError,match='corruption'):
        collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                as_of='2026-11-02',history_loader=fake)


def test_yfinance_invalid_data_fail_closed_without_cache(tmp_path):
    bad=sample_frame()
    bad.rows[0][1]['Close']='NaN'
    with pytest.raises(ValueError,match='Invalid OHLCV'):
        collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                history_loader=lambda *args:bad)
    assert not list(tmp_path.rglob('*.bin'))
    with pytest.raises(ValueError,match='empty'):
        collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                history_loader=lambda *args:Frame([]))
    with pytest.raises(RuntimeError,match='failed'):
        collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                history_loader=lambda *args:(_ for _ in ()).throw(RuntimeError('SECRET123')))
    assert not list(tmp_path.rglob('*.bin'))
    with pytest.raises(ValueError,match='Future'):
        collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                as_of='2027-01-01',history_loader=lambda *args:sample_frame())


def test_yahoo_canonical_import_hash_and_split_gate(tmp_path):
    meta=collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                 as_of='2026-11-02',history_loader=lambda *args:sample_frame(split=True))
    spec={'as_of':'2026-11-02','mode':EXTERNAL,'assets':[{
        'id':'TEST_YAHOO','name':'Mock unverified data','asset_type':'EQUITY',
        'sector':'Industry','oil_exposure':'none','venue':'XMIL','currency':'EUR',
        'prices_source':meta}]}
    bundle=tmp_path/'bundle';build_bundle(spec,bundle)
    report=screen(bundle)
    row=report['results'][0]
    assert row['market_score'] is None
    assert 'UNADJUSTED_SPLIT_REQUIRES_CORPORATE_ACTION_REVIEW' in row['warnings']
    assert row['status']=='INCOMPLETE_NO_RANK'
    meta2=dict(meta, source_url='https://evil.example.org/quote/TEST.MI/history/')
    with pytest.raises(ValueError,match='Yahoo Finance'):
        build_bundle({**spec,'assets':[{**spec['assets'][0],'prices_source':meta2}]},tmp_path/'bad')


def test_yahoo_without_split_allows_unverified_research_ranking(tmp_path):
    meta=collect(YFINANCE,'TEST.MI',tmp_path,acknowledge_yahoo_terms=True,
                 as_of='2026-11-02',history_loader=lambda *args:sample_frame())
    spec={'as_of':'2026-11-02','mode':EXTERNAL,'assets':[{
        'id':'TEST_YAHOO','name':'Mock unverified data','asset_type':'EQUITY',
        'sector':'Industry','oil_exposure':'none','venue':'XMIL','currency':'EUR',
        'prices_source':meta}]}
    bundle=tmp_path/'bundle';build_bundle(spec,bundle)
    row=screen(bundle)['results'][0]
    assert row['market_score'] is not None
    assert row['status']=='RESEARCH_RANK_UNVERIFIED_NOT_TRADE_READY'
    assert row['trade_ready'] is False


def test_public_workflows_do_not_publish_yahoo_price_history():
    """No public CI job may download and redistribute market-price files."""
    root=Path(__file__).resolve().parents[1]
    workflows=root/'.github/workflows'
    assert not (workflows/'refresh-manual.yml').exists()
    assert not (workflows/'manual-source-probe.yml').exists()
    manual=(workflows/'research.yml').read_text()
    assert 'investresearch refresh' not in manual
    assert 'refresh_history' not in manual
    assert 'reports/generated/REPORT.md' in manual
    assert 'path: reports/generated/' not in manual
    assert 'reports/generated/provider_history_unverified.csv' in manual  # never allowed
    ci=(workflows/'ci.yml').read_text()
    assert 'investresearch refresh' not in ci
    assert 'path: reports/generated/' not in ci
    assert 'data/research/demo' in ci
    # The local probe script remains opt-in, but is not automatically invoked on Actions.
    script=(root/'tools/smoke_free_sources.py').read_text()
    assert 'SEC_RESEARCH_CONTACT' in script
    assert 'print(contact)' not in script


def test_yahoo_symbol_rejects_dot_segments_before_touching_cache(tmp_path):
    """A ticker cannot escape or ambiguously address the cache directory."""
    called = []
    def fake(*args):
        called.append(args)
        return sample_frame()
    for invalid in ('.', '..', '...', '.cache', '..hidden', 'A..B'):
        with pytest.raises(ValueError, match='Invalid Yahoo symbol'):
            collect(YFINANCE, invalid, tmp_path, acknowledge_yahoo_terms=True,
                    history_loader=fake)
    assert not called
    assert not list(tmp_path.rglob('*.bin'))
    assert yahoo_source_url('BRK.B').endswith('/BRK.B/history/')
    assert yahoo_source_url('ENI.MI').endswith('/ENI.MI/history/')
