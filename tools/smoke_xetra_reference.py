"""One official Xetra reference-file audit on an ephemeral CI runner.

This is a DISCOVERY/SCHEMA smoke only, NOT historical prices, a data license,
or trading eligibility. No raw vendor files, instrument identifiers or holdings
are uploaded, printed or committed. A network block is reported separately
from a received malformed vendor snapshot.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from investresearch.research_xetra_universe import (
    MAX_BYTES, PROVIDER, parse_xetra,
)

URL = (
    "https://www.cashmarket.deutsche-boerse.com/resource/blob/"
    "1528/0447d5f72a1ca9cd3f00a6bd5f8805cc/data/"
    "t7-xetr-allTradableInstruments.csv"
)


def probe(*, transport=None, now=None):
    """Returns (classification, public aggregate summary); never a raw row."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise ValueError("Acquisition timestamp must be in UTC")
    try:
        if transport is not None:
            raw = transport(URL)
        else:
            request = Request(
                URL,
                headers={
                    "Accept": "text/csv",
                    "User-Agent": "InvestmentResearch-XetraReferenceAudit/1.0",
                },
            )
            with urlopen(request, timeout=18) as response:
                raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        return "SOURCE_UNAVAILABLE", None
    # Invalid data successfully returned by the provider is NOT a network outage.
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        return "VALIDATION_FAILED", {"reason": "Missing or oversized vendor CSV"}
    metadata = {
        "provider": PROVIDER,
        "source_url": URL,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at_utc": now.isoformat(),
        "encoding": "utf-8-sig",
    }
    try:
        _candidates, manifest = parse_xetra(raw, metadata, as_of=now.date())
    except (ValueError, UnicodeError, KeyError, TypeError, IndexError):
        return "VALIDATION_FAILED", {"reason": "Vendor CSV incompatible with strict XETR parser"}
    return "DISCOVERY_REFERENCE_VALIDATED", {
        "as_of": manifest["as_of"],
        "source_update_date": manifest["source_update_date"],
        "reference_count": manifest["candidate_count"],
        "by_source_type": manifest["source_type_counts"],
        "skipped_counts": manifest["skipped_counts"],
        "raw_sha256": manifest["source_raw_sha256"],
        "status": "UNRANKED_NO_PRICE_TAX_RIGHTS_OR_TRADE_CERTIFICATION",
    }


def main():
    classification, result = probe()
    print(f"XETRA_REFERENCE_CLASSIFICATION={classification}")
    if result:
        import json
        print(json.dumps(result, sort_keys=True))
    return {"DISCOVERY_REFERENCE_VALIDATED": 0,
            "SOURCE_UNAVAILABLE": 1, "VALIDATION_FAILED": 2}[classification]


if __name__ == "__main__":
    sys.exit(main())
