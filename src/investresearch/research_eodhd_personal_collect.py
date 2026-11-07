"""Optional zero-paid-API EODHD personal research collector, local private only.

This uses an operator-provided Free/Personal token from the environment.
No demo token is accepted for operational import. Exactly three API calls
per instrument (EOD, splits, dividends); no retries, no implicit paid API,
no bulk use or vendor data redistribution. Never call in public CI.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .quality import valid_isin
from .research_eodhd_pilot import (
    MAX_BYTES, SYMBOL, parse_eod, parse_splits, parse_dividends,
)
from .research_eodhd_local import (
    PROVIDER, SPLIT_PROVIDER, DIVIDEND_PROVIDER, ATTESTATION, MAPPING,
    VENUE_TO_EXCHANGE, _private_path, normalize_private_eodhd,
)

MAX_REPORT_BYTES = 300_000
SCHEMA = "r004-eodhd-private-source-acquisition-v1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Price provider redirect prohibited")


def _get_one(kind, symbol, start, end, token, opener):
    if kind not in MAX_BYTES:
        raise ValueError("Unsupported price source endpoint")
    clean = f"https://eodhd.com/api/{kind}/{symbol}"
    args = {"api_token": token, "from": start.isoformat(),
            "to": end.isoformat(), "fmt": "json"}
    if kind == "eod":
        args["period"] = "d"
    url = clean + "?" + urllib.parse.urlencode(args)
    request = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "InvestmentResearch-Personal/1.0"})
    try:
        with opener.open(request, timeout=18) as response:
            if response.geturl().split("?")[0] != clean:
                raise ValueError("Unrecognised market data response URL")
            payload = response.read(MAX_BYTES[kind]+1)
    except (urllib.error.URLError, OSError, TimeoutError):
        # Do not leak token, URL-with-secret or vendor body into logs.
        raise RuntimeError("Personal EODHD source unavailable or not entitled") from None
    if not 1 <= len(payload) <= MAX_BYTES[kind]:
        raise ValueError("EODHD response missing/oversized")
    return payload


def collect_one(*, symbol, isin, venue, currency, instrument_name,
                asset_type, sector, oil_exposure, output, repo_root,
                api_token, personal_rights_ack=False,
                identity_review_ack=False, as_of=None, opener=None):
    """Acquire one private symbol's three snapshots with verified local scope.

    Operator MUST independently check instrument ISIN/MIC and subscription
    rights. These acknowledgements are not a data-provider/broker certificate.
    The output is a raw local spec usable with 'investresearch-b build'.
    """
    if personal_rights_ack is not True:
        raise ValueError("Explicit individual noncommercial EODHD terms acknowledgement required")
    if identity_review_ack is not True:
        raise ValueError("Manual two-source ISIN/venue identity review required")
    if not isinstance(api_token,str) or not api_token.strip() or api_token.strip().lower()=="demo":
        raise ValueError("Personal EODHD free-account token required, not demo")
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid explicit symbol")
    if not valid_isin(isin) or venue not in VENUE_TO_EXCHANGE:
        raise ValueError("Valid ISIN and supported venue must be reviewed")
    if currency not in ("EUR", "USD") or not symbol.endswith("." + VENUE_TO_EXCHANGE[venue]):
        raise ValueError("Provider symbol/venue/currency mismatch")
    if not isinstance(instrument_name,str) or not 0 < len(instrument_name.strip()) <= 200:
        raise ValueError("Issuer name must be explicit")
    if not isinstance(sector,str) or not 0 < len(sector.strip()) <= 100:
        raise ValueError("Issuer sector must be explicitly investigated")
    if not isinstance(asset_type,str) or asset_type not in {
        "EQUITY","ETF_LEGAL_STATUS_UNVERIFIED","ETC","ETN",
    }:
        raise ValueError("Asset type requires an explicitly reviewed legal class")
    if oil_exposure not in ("none","indirect","material","primary","unknown"):
        raise ValueError("Ethical oil exposure must be reviewed")
    now = datetime.now(timezone.utc)
    cutoff = as_of or now.date()
    if cutoff != now.date():
        raise ValueError("Personal source intake must be dated actual UTC acquisition day")
    root = Path(repo_root).resolve()
    out = _private_path(output, root)
    if out.exists():
        raise ValueError("Use a new private source folder; no overwrites")
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect())
    start = cutoff - timedelta(days=340)
    payloads = {
        kind: _get_one(kind, symbol, start, cutoff, api_token, opener)
        for kind in ("eod", "splits", "div")
    }
    bars = parse_eod(payloads["eod"], as_of=cutoff)
    splits = parse_splits(payloads["splits"], as_of=cutoff)
    dividends = parse_dividends(payloads["div"], as_of=cutoff, currency=currency)
    if len(bars) < 61:
        raise ValueError("61 source sessions unavailable; cannot build research history")
    if bars[-1]["date"] > cutoff:
        raise ValueError("Future EOD price rejected")
    # The collector only creates an offline input; it does not make a price
    # research score, assert dataset entitlement or schedule API requests.
    out.mkdir(parents=True)
    stamp = datetime.now(timezone.utc).isoformat()
    names = {"eod":"eod.json","splits":"splits.json","div":"dividends.json"}
    for kind, filename in names.items():
        (out/filename).write_bytes(payloads[kind])
    def source(kind, provider):
        data = payloads[kind]
        return {
            "provider": provider,
            "path": str(out/names[kind]),
            "source_url": f"https://eodhd.com/api/{kind}/{symbol}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "retrieved_at_utc": stamp,
        }
    price = {
        **source("eod", PROVIDER), "symbol": symbol,
        "isin": isin, "venue": venue, "currency": currency,
        "usage_attestation": ATTESTATION,
        "identity_evidence_status": MAPPING,
        "splits_source": source("splits", SPLIT_PROVIDER),
        "dividends_source": source("div", DIVIDEND_PROVIDER),
    }
    asset = {
        "id": isin, "name": instrument_name.strip(), "isin": isin,
        "asset_type": asset_type, "sector": sector.strip(),
        "venue": venue, "currency": currency,
        "oil_exposure": oil_exposure,
        "prices_source": price,
    }
    spec = {"mode": "EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE",
            "as_of": cutoff.isoformat(), "assets": [asset]}
    # Validate offline adapter immediately against all three saved payloads.
    normalized, source_note = normalize_private_eodhd(
        price, payloads["eod"], cutoff, asset, repo_root=root)
    report = {
        "schema_version": SCHEMA,
        "source_as_of": cutoff.isoformat(),
        "symbol": symbol, "isin": isin, "venue": venue,
        "asset_type": asset_type,
        "source_eod_sessions": len(bars),
        "normalized_sessions": len(normalized),
        "source_split_events": len(splits),
        "source_dividend_events": len(dividends),
        "raw_sources_sha256": {
            kind: hashlib.sha256(data).hexdigest()
            for kind, data in payloads.items()},
        "corporate_actions_independently_verified": False,
        "license_entitlement_independently_verified": False,
        "issuer_identity_independently_verified": False,
        "market_data_is_private": True,
        "trade_ready": False,
        "next_step": "Offline build with this local spec, verify brokerage and corporate actions independently",
    }
    (out/"BUNDLE_INPUT_SPEC.json").write_text(
        json.dumps(spec,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    (out/"SOURCE_INTAKE_AUDIT.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return report
