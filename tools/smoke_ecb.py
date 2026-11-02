"""Optional public ECB live source compatibility smoke, no secrets or paid APIs.

Never used as a substitute for the deterministic offline test suite.
"""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from investresearch.research_sources import collect, parse_ecb


def main():
    with TemporaryDirectory() as tmp:
        meta=collect('ECB_EUR_FX','',Path(tmp))
        raw=Path(meta['path']).read_bytes()
        parsed=parse_ecb(raw,date.today())
        print(f"ECB live smoke PASSED: {len(parsed)} historical USD reference observations; latest={parsed[-1]['date']}; sha256={meta['sha256']}")


if __name__=='__main__':main()
