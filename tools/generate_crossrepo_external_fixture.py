"""Generate test-only fabricated EXTERNAL-mode B bundle for A↔B integration CI.

Real Block B/A code is exercised, but **NO MARKET DATA** is produced. This
script may run ONLY on isolated CI/private scratch directories whose names
include 'synthetic_fixture'. It is not a provider connector or trade signal.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import date, timedelta
from pathlib import Path

from investresearch.market_calendar import session
from investresearch.research_bundle import build_bundle, EXTERNAL
from investresearch.research_sources import ECB_CSV_URL

AS_OF = date(2026, 11, 5)
INSTRUMENTS = (
    ("US0378331005", "MOCK_A", "TECHNOLOGY", 110, .095),
    ("US5949181045", "MOCK_B", "SOFTWARE", 138, .044),
)


def generate(root: Path):
    root = root.resolve()
    if "synthetic_fixture" not in str(root) or root.exists():
        raise ValueError("Must create a NEW synthetic_fixture-only scratch output")
    root.mkdir(parents=True)
    start = date(2026, 7, 1)
    days = [start + timedelta(days=i)
            for i in range((AS_OF-start).days+1)]
    nasdaq_days = [d for d in days if session(d, "XNAS")]
    assert len(nasdaq_days) > 61

    assets = []
    for isin, symbol, sector, level, slope in INSTRUMENTS:
        rows = []
        for i, day in enumerate(nasdaq_days):
            # Declared fictional prices; stable source-schema fixtures only.
            price = level + slope * i + (i % 7) * .037
            rows.append({
                "date": day.isoformat()+"T00:00:00Z",
                "open": price, "high": price*1.008,
                "low": price*.992, "close": price,
                "adjOpen": price, "adjHigh": price*1.008,
                "adjLow": price*.992, "adjClose": price,
                "volume": 130_000, "adjVolume": 130_000,
                "divCash": 0, "splitFactor": 1,
            })
        original = json.dumps(rows, separators=(",", ":")).encode("utf-8")
        source_path = root/f"{isin}.json"
        source_path.write_bytes(original)
        assets.append({
            "id":f"TEST_ONLY_{isin}", "name":f"NOT_MARKET_DATA_{symbol}",
            "isin":isin, "asset_type":"EQUITY",
            "venue":"XNAS", "currency":"USD",
            "sector":sector, "oil_exposure":"none",
            "prices_source": {
                "provider":"TIINGO_EOD_PERSONAL_RESEARCH",
                "source_url":f"https://api.tiingo.com/tiingo/daily/{symbol}/prices",
                "path":str(source_path),
                "sha256":hashlib.sha256(original).hexdigest(),
                "retrieved_at_utc":"2026-11-05T20:00:00Z",
                "usage_attestation":"PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED",
                "identity_evidence_status":"TWO_SOURCE_ISIN_SYMBOL_VENUE_MANUALLY_REVIEWED",
                "symbol":symbol, "isin":isin, "venue":"XNAS",
                "currency":"USD",
            },
        })

    fx_days = [d for d in days if d.weekday() < 5]
    # Fictional source bytes in official ECB CSV *schema*. Not ECB prices.
    fx_source = ("Date,USD\n" +
                 "".join(f"{d.isoformat()},1.14\n" for d in fx_days)).encode("utf-8")
    fx_path = root/"SYNTHETIC_NOT_ECB.csv"
    fx_path.write_bytes(fx_source)
    spec = {
        "mode": EXTERNAL,
        "as_of": AS_OF.isoformat(),
        "assets": assets,
        "fx_source": {
            "provider":"ECB_EUR_FX",
            "source_url": ECB_CSV_URL,
            "sha256":hashlib.sha256(fx_source).hexdigest(),
            "path":str(fx_path),
            "retrieved_at_utc":"2026-11-05T20:00:00Z",
        },
    }
    spec_file = root/"SYNTHETIC_TEST_ONLY_SPEC.json"
    spec_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    bundle = root/"SYNTHETIC_TEST_ONLY_EXTERNAL_BRANCH_BUNDLE"
    manifest = build_bundle(spec, bundle)
    assert manifest["mode"] == EXTERNAL
    assert len(manifest["assets"]) == 2
    # Fake official-SCHEMA reference catalogs for R-006 interoperability.
    # These bytes are invented. Official-looking source_url fields are only
    # parser-contract fixtures and must NEVER be treated as source attestations.
    from investresearch.research_sources import SEC_TICKERS_URL
    from investresearch.research_xetra_universe import PROVIDER as XETRA_PROVIDER
    xetra_url=("https://www.cashmarket.deutsche-boerse.com/resource/blob/"
       "1528/0447d5f72a1ca9cd3f00a6bd5f8805cc/data/"
       "t7-xetr-allTradableInstruments.csv")
    xbuf=io.StringIO(newline="")
    writer=csv.writer(xbuf,delimiter=";",lineterminator="\n")
    writer.writerow(["Product Status","Instrument Status","Instrument","ISIN",
                     "Mnemonic","MIC Code","Settlement Currency","Instrument Type"])
    writer.writerow(["Active","Active","FICTITIOUS-XETRA-REFERENCE",
                     "US0378331005","FCT","XETR","EUR","CS"])
    writer.writerow(["Active","Active","FICTITIOUS-ETF-REFERENCE",
                     "IE00B4L5Y983","FCTETF","XETR","EUR","ETF"])
    xraw=("Market:;XETR\nDate Last Update:;04.11.2026\n"+xbuf.getvalue()).encode()
    (root/"FICTIONAL_XETRA_T7.csv").write_bytes(xraw)
    (root/"FICTIONAL_XETRA_META.json").write_text(json.dumps({
       "provider":XETRA_PROVIDER,"source_url":xetra_url,
       "sha256":hashlib.sha256(xraw).hexdigest(),
       "retrieved_at_utc":"2026-11-05T16:00:00Z",
       "fixture_only":True,
    }))
    sec=json.dumps({"fields":["cik","name","ticker","exchange"],"data":[
        [1,"FICTIONAL_SEC_COMPANY_A","MOCK_A","Nasdaq"],
        [2,"FICTIONAL_SEC_COMPANY_B","MOCK_B","NYSE"]]}).encode()
    (root/"FICTIONAL_SEC_CATALOG.json").write_bytes(sec)
    (root/"FICTIONAL_SEC_META.json").write_text(json.dumps({
        "provider":"SEC_TICKERS","source_url":SEC_TICKERS_URL,
        "sha256":hashlib.sha256(sec).hexdigest(),
        "retrieved_at_utc":"2026-11-05T16:00:00Z",
        "fixture_only":True,
    }))
    (root/"THIS_IS_NOT_MARKET_DATA.txt").write_text(
        "FICTITIOUS TEST PRICES AND FX. Not issuer evidence, "
        "source rights, market results, investment rankings or trading.\n",
        encoding="utf-8",
    )
    return bundle


def main():
    parser = argparse.ArgumentParser(description="Synthetic EXTERNAL-mode crossrepo regression only")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    result = generate(options.output)
    print("EXTERNAL_CODEPATH_FIXTURE_GENERATED_NOT_MARKET_DATA=PASS")
    print(f"BUNDLE_FOR_CROSSREPO_TEST={result}")


if __name__ == "__main__":
    main()
