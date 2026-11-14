"""Create intentionally synthetic, repeatable OHLC/FX/fundamental examples."""
from __future__ import annotations
import argparse
import csv
import json
import math
import sys
import tempfile
from datetime import date,timedelta
from pathlib import Path
from .market_calendar import session
from .research_bundle import build_bundle,SYNTHETIC

ROOT=Path(__file__).resolve().parents[2]
AS_OF=date(2026,11,1)


def _csv(path,columns,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=columns,lineterminator='\n');w.writeheader();w.writerows(records)


def _days(venue):
    start=date(2026,5,1)
    return [start+timedelta(days=i) for i in range((AS_OF-start).days+1)
            if session(start+timedelta(days=i),venue)]


def create(outdir=ROOT/'data/research/demo'):
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);assets=[]
        patterns=[
          ('DEMO_GRID','Synthetic grid equipment','XMIL','EUR','Electrification','none',.0012,0,False,False),
          ('DEMO_HEALTH','Synthetic healthcare company','XMIL','EUR','Healthcare','none',.0007,1,True,False),
          ('DEMO_TECH','Synthetic US semiconductor','XNAS','USD','Semiconductors','none',.0018,2,True,False),
          ('DEMO_OIL','Synthetic petroleum producer','XMIL','EUR','Oil','direct',.003,3,True,False),
          ('DEMO_SHORT','Synthetic newly listed issuer','XMIL','EUR','Industrials','none',.001,4,False,True),
          ('DEMO_ETF','Synthetic diversified ETF','XMIL','EUR','Index fund','none',.0004,5,False,False),
          ('DEMO_WEAK','Synthetic negative earnings company','XMIL','EUR','Industry','none',-.0007,6,True,False),
        ]
        for uid,name,venue,ccy,sector,oil,slope,seed,with_fund,short in patterns:
            days=_days(venue)
            if short:days=days[-22:]
            bars=[]
            for k,d in enumerate(days):
                noise=2.1*math.sin((k+seed*3)/11)+.7*math.cos((k+seed)/3.5)
                p=max(1,round(25+seed*6 + (k*100*slope)+noise,4))
                bars.append({'date':str(d),'close':f'{p:.4f}','volume':str(25000+seed*1300+(k%13)*2000)})
            price=root/(uid+'.csv');_csv(price,['date','close','volume'],bars)
            a={'id':uid,'name':name,'venue':venue,'currency':ccy,'sector':sector,
               'oil_exposure':oil,'asset_type':'ETF_UCITS' if uid=='DEMO_ETF' else 'EQUITY',
               'index_memberships':[],'prices_source':{
                   'provider':'SYNTHETIC_PRICES','path':str(price)}}
            if with_fund:
                data={'period_end':'2025-12-31','revenue_usd':str(100000000+seed*25000000),
                      'net_income_usd':str(15000000 if uid!='DEMO_WEAK' else -13000000),
                      'revenue_filed_date':'2026-02-15','earnings_filed_date':'2026-02-15'}
                f=root/(uid+'.json');f.write_text(json.dumps(data),encoding='utf-8')
                a['fundamentals_source']={'provider':'SYNTHETIC_FUNDAMENTALS','path':str(f)}
            assets.append(a)
        # Synthetic ECB-like rates aligned to each US session, NOT real ECB observations.
        fx=root/'fx.csv';fxdays=sorted(set(_days('XNYS'))|set(_days('XMIL')))
        _csv(fx,['date','usd_per_eur'],[{'date':str(d),'usd_per_eur':f'{1.08+0.015*math.sin(k/19):.6f}'}
              for k,d in enumerate(fxdays)])
        events=root/'events.csv'
        _csv(events,['event_id','asset_id','event_date','published_date','category','description','source_url'],[
            {'event_id':'DEMO_MACRO','asset_id':'*','event_date':'2026-11-03','published_date':'2026-10-21',
             'category':'macro','description':'Fictional central bank discussion; NOT an actual calendar event',
             'source_url':''},
            {'event_id':'DEMO_TECH_EVENT','asset_id':'DEMO_TECH','event_date':'2026-11-05','published_date':'2026-10-20',
             'category':'earnings','description':'Synthetic earnings release demonstration; NOT an actual issuer event',
             'source_url':''}])
        spec={'as_of':AS_OF.isoformat(),'mode':SYNTHETIC,'assets':assets,
              'events_source':{'provider':'SYNTHETIC_EVENTS','path':str(events)},
              'fx_source':{'provider':'SYNTHETIC_FX','path':str(fx)}}
        return build_bundle(spec,outdir)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'data/research/demo')
    args=ap.parse_args()
    result=create(args.out)
    print('Generated synthetic research bundle with',len(result['assets']),'assets')
