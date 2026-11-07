"""Explicit Tiingo Starter/Personal EOD collection, local private only.

One bounded request per source-defined US equity/ETF identity. The token is
never placed in a URL, CLI argument, log or GitHub artifact. No polling,
retries, streaming, paid API fallback, provider account creation or hidden
network requests. Historical prices remain provider-supplied and NOT verified
for a particular user's brokerage or data licence by this software.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .quality import valid_isin
from .research_tiingo_local import (
    PROVIDER, ATTESTATION, MAPPING, SYMBOL, VENUES, MAX_BYTES,
    parse_tiingo, normalize_private_tiingo,
)

VERSION = "r004-tiingo-personal-source-intake-v1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unapproved Tiingo redirect")


def collect_one(*, symbol, isin, venue, instrument_name, asset_type,
                sector, oil_exposure, output, repo_root, api_token,
                personal_rights_ack=False, identity_review_ack=False,
                opener=None):
    """Only a *mocked* original-schema adapter regression remains available.

    Live Starter collection is blocked because currently published ToS 1.6(a)
    forbids persistent raw-data/derived-data storage on Starter/trials.
    """
    if opener is None:
        raise ValueError("TIINGO_STARTER_PERSISTENT_STORAGE_NOT_PERMITTED: no live free-tier collector. Use explicitly licensed non-Tiingo original sources.")
    if personal_rights_ack is not True:
        raise ValueError("Explicit personal-use Tiingo terms acceptance is required")
    if identity_review_ack is not True:
        raise ValueError("Two-source manual ISIN/venue identity verification required")
    if not isinstance(api_token, str) or not api_token.strip() or api_token.lower() == "demo":
        raise ValueError("Personal Tiingo account token required")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid Tiingo symbol")
    if not valid_isin(isin) or venue not in VENUES:
        raise ValueError("Valid ISIN and exchange venue required")
    if asset_type not in ("EQUITY", "ETF_LEGAL_STATUS_UNVERIFIED"):
        raise ValueError("Tiingo EOD US scope currently equities/legally unclassified ETFs")
    if not isinstance(instrument_name, str) or not 0 < len(instrument_name.strip()) <= 200:
        raise ValueError("Reviewed nonempty instrument name required")
    if not isinstance(sector, str) or not 0 < len(sector.strip()) <= 100:
        raise ValueError("Reviewed sector required")
    if oil_exposure not in ("none", "indirect", "material", "primary", "unknown"):
        raise ValueError("Ethical exposure classification must be explicit")
    repo = Path(repo_root).resolve()
    output = Path(output).expanduser().resolve()
    if output.is_relative_to(repo) and not output.is_relative_to(repo/"data/private"):
        raise ValueError("Inside repo, personal data output must be data/private")
    if output.exists():
        raise ValueError("Use new untouched output; no overwriting source evidence")
    now = datetime.now(timezone.utc)
    start = now.date() - timedelta(days=350)
    end = now.date()
    clean_url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
    query = urllib.parse.urlencode({
        "startDate":start.isoformat(), "endDate":end.isoformat(),
        "format":"json", "resampleFreq":"daily",
    })
    req = urllib.request.Request(
        clean_url+"?"+query,
        headers={
            "Accept":"application/json",
            "Authorization":"Token "+api_token,
            "User-Agent":"InvestmentResearch-TiingoPersonal/1.0",
        },
        method="GET",
    )
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(req, timeout=18) as response:
            if response.geturl().split("?")[0] != clean_url:
                raise ValueError("Unrecognised provider redirect")
            payload = response.read(MAX_BYTES+1)
    except (OSError, urllib.error.URLError, TimeoutError):
        # No source response, Authorization header or user URL in errors.
        raise RuntimeError("Tiingo source request failed/was not entitled") from None
    dates = parse_tiingo(payload, as_of=end)
    if len(dates) < 61:
        raise ValueError("Tiingo account did not return 61 dated sessions")
    raw_sha = hashlib.sha256(payload).hexdigest()
    stamp = datetime.now(timezone.utc).isoformat()
    output.mkdir(parents=True)
    raw_path = output/"tiingo_eod_original.json"
    raw_path.write_bytes(payload)
    source = {
        "provider":PROVIDER,
        "path":str(raw_path),
        "source_url":clean_url,
        "sha256":raw_sha,
        "retrieved_at_utc":stamp,
        "usage_attestation":ATTESTATION,
        "identity_evidence_status":MAPPING,
        "symbol":symbol, "isin":isin, "venue":venue, "currency":"USD",
    }
    asset = {
        "id":isin, "name":instrument_name.strip(), "isin":isin,
        "asset_type":asset_type, "sector":sector.strip(),
        "venue":venue, "currency":"USD",
        "oil_exposure":oil_exposure, "prices_source":source,
    }
    checked, note = normalize_private_tiingo(
        source, payload, end, asset, repo_root=repo)
    spec = {
        "mode":"EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE",
        "as_of":end.isoformat(), "assets":[asset],
    }
    audit = {
        "schema_version":VERSION,
        "as_of":end.isoformat(),
        "retrieved_at_utc":stamp,
        "isin":isin, "symbol":symbol, "venue":venue,
        "eod_source_sha256":raw_sha,
        "source_sessions":len(dates),
        "normalized_sessions":len(checked),
        "split_events_reported":len(note["split_dates"]),
        "dividend_events_reported":note["source_dividend_event_count"],
        "usage_rights_independently_verified":False,
        "identity_broker_confirmed":False,
        "corporate_actions_independently_verified":False,
        "research_market_score":None,
        "trade_ready":False,
        "next_step":"Apply independently obtained dated ECB FX and check as-of, venue and issuer events offline",
    }
    (output/"BUNDLE_INPUT_SPEC.json").write_text(
        json.dumps(spec, sort_keys=True, ensure_ascii=False, indent=2)+"\n",
        encoding="utf-8")
    (output/"SOURCE_INTAKE_AUDIT.json").write_text(
        json.dumps(audit, sort_keys=True, ensure_ascii=False, indent=2)+"\n",
        encoding="utf-8")
    return audit
