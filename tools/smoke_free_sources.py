"""Strict, user-triggered provider probe. No raw source files or secrets printed."""
from __future__ import annotations
import argparse
import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from investresearch.research_sources import (YFINANCE, collect, parse_ohlcv,
    parse_sec_fundamentals, sha256_bytes)
from investresearch.research_universe import parse_sec_tickers


def check_sec(cache:Path):
    contact=os.environ.get('SEC_RESEARCH_CONTACT','')
    if not contact:raise RuntimeError('Missing SEC_RESEARCH_CONTACT repository secret')
    catalog=collect('SEC_TICKERS','',cache,sec_contact=contact)
    cbytes=Path(catalog['path']).read_bytes()
    tickers=parse_sec_tickers(cbytes)
    print(f'SEC catalog PASS: {len(tickers)} candidates, sha256={catalog["sha256"]}')
    facts=collect('SEC_COMPANYFACTS','0000320193',cache,sec_contact=contact)
    fbytes=Path(facts['path']).read_bytes()
    accounting=parse_sec_fundamentals(fbytes,date.today())
    print(f'SEC Apple 10-K PASS: fiscal_year_end={accounting["period_end"]}, '+
          f'filed_date={accounting["revenue_filed_date"]}, sha256={facts["sha256"]}')


def check_yfinance(cache:Path,symbol:str,acknowledged:bool):
    if not acknowledged:
        raise RuntimeError('Yahoo personal-use terms must be explicitly acknowledged')
    result=collect(YFINANCE,symbol,cache,acknowledge_yahoo_terms=True)
    prices=parse_ohlcv(Path(result['path']).read_bytes(),date.today())
    print(f'Yahoo via yfinance UNVERIFIED: {len(prices)} OHLCV rows, last={prices[-1]["date"]}, '+
          f'splits={len(result["split_dates"])}, sha256={result["sha256"]}')
    if len(prices)<61:raise RuntimeError('Insufficient observations for screening')


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',choices=['sec','yfinance','both'],required=True)
    parser.add_argument('--symbol',default='AAPL')
    parser.add_argument('--acknowledge-yahoo-terms',action='store_true')
    args=parser.parse_args(argv)
    with TemporaryDirectory(prefix='source-probe-') as temp:
        cache=Path(temp)
        if args.source in ('sec','both'):check_sec(cache)
        if args.source in ('yfinance','both'):
            check_yfinance(cache,args.symbol,args.acknowledge_yahoo_terms)


if __name__=='__main__':main()
