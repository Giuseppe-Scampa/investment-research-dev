"""One explicitly authorized EODHD XETRA reference catalog request (no prices).

Vendor source is stored privately and never published to Actions/artifacts.
The source list is NOT an entitlement, independently verified ISIN mapping,
broker venue, UCITS legal classification or rankable historical dataset.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .research_eodhd_xetra_crosswalk import (
    PROVIDER, MAX_BYTES, parse_eodhd_xetra_catalog,
)

SCHEMA = "r006-eodhd-xetra-catalog-intake-v1"
URL = "https://eodhd.com/api/exchange-symbol-list/XETRA"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected vendor redirect")


def collect_catalog(*, output, repo_root, api_token,
                    personal_rights_ack=False, opener=None):
    if personal_rights_ack is not True:
        raise ValueError("Personal EODHD data-use rights acknowledgement required")
    if not isinstance(api_token, str) or not api_token.strip() or api_token.strip().lower() == "demo":
        raise ValueError("EODHD personal account key required; demo disallowed")
    path = Path(output).expanduser().resolve()
    repo = Path(repo_root).resolve()
    if path.is_relative_to(repo) and not path.is_relative_to(repo/"data/private"):
        raise ValueError("Vendor catalog in a repository must be private")
    if path.exists():
        raise ValueError("No overwriting existing EODHD catalog")
    request = urllib.request.Request(
        URL + "?" + urllib.parse.urlencode({"api_token": api_token, "fmt": "json"}),
        headers={"Accept":"application/json", "User-Agent":"InvestmentResearch-ReferenceCoverage/1.0"},
    )
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=18) as response:
            if response.geturl().split("?")[0] != URL:
                raise ValueError("Invalid vendor response destination")
            payload = response.read(MAX_BYTES + 1)
    except (OSError, TimeoutError, urllib.error.URLError):
        raise RuntimeError("EODHD XETRA symbol catalog unavailable or not entitled") from None
    stamped = datetime.now(timezone.utc)
    meta = {
        "provider": PROVIDER,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source_url": URL,
        "retrieved_at_utc": stamped.isoformat(),
        "usage_attestation":"PERSONAL_NONCOMMERCIAL_PRIVATE_LOCAL_USE_RIGHTS_ASSERTED",
    }
    entries, info = parse_eodhd_xetra_catalog(payload, meta, as_of=stamped.date())
    path.mkdir(parents=True)
    (path/"EODHD_XETRA_RAW.json").write_bytes(payload)
    (path/"EODHD_XETRA_SOURCE.json").write_text(
        json.dumps(meta,sort_keys=True,indent=2)+"\n", encoding="utf-8")
    report = {
        "schema_version":SCHEMA, "as_of":stamped.date().isoformat(),
        "provider":PROVIDER, "provider_records":info["total_vendor_rows"],
        "usable_isin_records":info["usable_isin_vendor_rows"],
        "excluded_reference_rows":info["skipped_vendor"],
        "snapshot_sha256":meta["sha256"],
        "price_histories":0, "broker_approved":False,
        "source_rights_independently_verified":False, "trade_ready":False,
        "next_step":"Crosswalk with the real offline official Xetra reference under data/private",
    }
    (path/"CATALOG_AUDIT.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return report
