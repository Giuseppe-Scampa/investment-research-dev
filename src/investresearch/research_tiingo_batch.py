"""M3 free-source batch: 2–20 personally verified US symbols per explicit run.

One Tiingo Starter REST call per ISIN, no automatic retries, sleeps, polling,
paid fallback or account creation. A free Personal account/token and
independently verified ISIN mapping are still required. Source bodies PRIVATE.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from .quality import valid_isin
from .research_tiingo_personal_collect import collect_one
from .research_intake_merge import combine

VERSION="r004-tiingo-free-bounded-batch-v1"
ALLOWED={"isin","symbol","venue","instrument_name","asset_type",
         "sector","oil_exposure","reference_urls"}
MAX_PER_RUN=20
MAX_SPEC_BYTES=30_000


def _validate_sources(rows):
    if not isinstance(rows,list) or not 2<=len(rows)<=MAX_PER_RUN:
        raise ValueError("Provide 2–20 independently reviewed US instruments only")
    seen_isin,seen_symbol=set(),set()
    prepared=[]
    for item in rows:
        if not isinstance(item,dict) or set(item)!=ALLOWED:
            raise ValueError("Unexpected reviewed instrument schema; secrets not accepted")
        isin,symbol=item["isin"],item["symbol"]
        if not valid_isin(isin) or not isinstance(symbol,str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,29}",symbol):
            raise ValueError("Invalid reviewed ISIN or Tiingo symbol")
        if isin in seen_isin or symbol.upper() in seen_symbol:
            raise ValueError("Duplicate ISIN/ticker in private intake manifest")
        seen_isin.add(isin);seen_symbol.add(symbol.upper())
        if (item["venue"] not in ("XNYS","XNAS")
                or item["asset_type"] not in ("EQUITY","ETF_LEGAL_STATUS_UNVERIFIED")
                or item["oil_exposure"] not in ("none","indirect","material","primary","unknown")
                or not isinstance(item["sector"],str) or not item["sector"].strip()
                or not isinstance(item["instrument_name"],str)
                or not item["instrument_name"].strip()):
            raise ValueError("Instrument venue/legal class/sector/ethical exposure unreviewed")
        references=item["reference_urls"]
        if not isinstance(references,list) or len(references)!=2:
            raise ValueError("Two public issuer/exchange identity reference URLs required")
        domains=set()
        for link in references:
            if not isinstance(link,str) or len(link)>600:
                raise ValueError("Invalid reference URL")
            u=urlsplit(link)
            if u.scheme!="https" or not u.hostname or u.username or u.password or u.fragment:
                raise ValueError("Reference must be plain HTTPS provenance")
            domains.add(u.hostname.lower())
        if len(domains)!=2:
            raise ValueError("Identity references must have distinct domains")
        prepared.append(item)
    return sorted(prepared,key=lambda x:x["isin"])


def collect_batch(*, manifest_path, output, repo_root, api_token,
                  personal_rights_ack=False, identity_review_ack=False,
                  opener=None):
    if personal_rights_ack is not True or identity_review_ack is not True:
        raise ValueError("Personal-use terms and two-source mapping review mandatory")
    if not isinstance(api_token,str) or not api_token.strip() or api_token.strip().lower()=="demo":
        raise ValueError("Free Tiingo personal token must be configured privately")
    root=Path(repo_root).resolve()
    manifest=Path(manifest_path).expanduser().resolve()
    folder=Path(output).expanduser().resolve()
    if any(p.is_relative_to(root) and not p.is_relative_to(root/"data/private")
           for p in (manifest,folder)):
        raise ValueError("User/vendor research files inside repository must be private")
    if not manifest.is_file() or not 0<manifest.stat().st_size<=MAX_SPEC_BYTES:
        raise ValueError("Missing/oversized reviewed source input")
    if folder.exists():
        raise ValueError("Use a NEW private batch output; never silently reuse account quota")
    data=manifest.read_bytes()
    try:
        body=json.loads(data)
    except (ValueError,UnicodeError):
        raise ValueError("Malformed reviewed batch file") from None
    if not isinstance(body,dict) or set(body)!={"schema_version","instruments"} or body["schema_version"]!=VERSION:
        raise ValueError("Unknown reviewed batch format")
    chosen=_validate_sources(body["instruments"])
    # All preflight validations run before the FIRST remote provider request.
    folder.mkdir(parents=True)
    original_specs=[]
    audits=[]
    for row in chosen:
        dest=folder/row["isin"]
        result=collect_one(
            symbol=row["symbol"],isin=row["isin"],venue=row["venue"],
            instrument_name=row["instrument_name"],
            asset_type=row["asset_type"],sector=row["sector"],
            oil_exposure=row["oil_exposure"],output=dest,repo_root=root,
            api_token=api_token,personal_rights_ack=True,
            identity_review_ack=True,opener=opener)
        original_specs.append(dest/"BUNDLE_INPUT_SPEC.json")
        audits.append({
            "isin_sha256":hashlib.sha256(row["isin"].encode()).hexdigest(),
            "source_eod_sha256":result["eod_source_sha256"],
            "sessions":result["source_sessions"],
            "references_operator_supplied_not_independently_checked":row["reference_urls"],
        })
    merged=folder/"TIINGO_MULTI_SOURCE_SPEC.json"
    merge_report=combine(
        source_specs=original_specs,output=merged,repo_root=root)
    audit={
        "schema_version":VERSION,
        "status":"PRIVATE_SOURCE_INTAKE_NOT_TRADE_READY",
        "individual_source_count":len(audits),
        "total_tiingo_requests_this_batch":len(audits),
        "source_manifest_sha256":hashlib.sha256(data).hexdigest(),
        "candidate_source_audits":audits,
        "merged_source_sha256":merge_report["output_sha256"],
        "licence_checked_by_provider":False,
        "identity_verified_by_broker":False,
        "fx_bound":False,
        "trade_ready":False,
        "next_step":"Bind dated official ECB FX to TIINGO_MULTI_SOURCE_SPEC.json, then build/screen/tactical/risk privately",
    }
    (folder/"TIINGO_BATCH_AUDIT_NOT_TRADE_READY.json").write_text(
        json.dumps(audit,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return audit
