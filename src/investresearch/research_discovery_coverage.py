"""R-006/M4: independent SEC/Xetra discovery coverage vs source-screened assets.

The official listing catalogs are UNRANKED. SEC listing data does not
contain ISINs, hence no ticker-based identity is invented. Xetra only
allows exact ISIN+MIC+currency evidence, not proof of price rights,
corporate action, investment classification, or eligibility to trade.
No external network, billing, broker data, AI, or hidden price collection.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .research_universe import parse_sec_tickers
from .research_xetra_universe import parse_xetra
from .research_bundle import SYNTHETIC, EXTERNAL
from .research_sources import SEC_TICKERS_URL
from .quality import valid_isin

VERSION="r006-independent-discovery-coverage-v1"


def _sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,
        separators=(",",":")).encode("utf-8")).hexdigest()


def _original(path,meta, *, repo_root, cap):
    rawfile=Path(path).expanduser().resolve()
    metafile=Path(meta).expanduser().resolve()
    root=Path(repo_root).resolve()
    for p in (rawfile,metafile):
        if p.is_relative_to(root) and not p.is_relative_to(root/"data/private"):
            raise ValueError("External public reference snapshots inside repo must remain data/private")
        if not p.is_file() or not 0<p.stat().st_size<=cap:
            raise ValueError("Missing/oversized original reference source")
    raw=rawfile.read_bytes()
    try:
        metadata=json.loads(metafile.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError):
        raise ValueError("Malformed reference source metadata") from None
    if not isinstance(metadata,dict) or metadata.get("sha256")!=hashlib.sha256(raw).hexdigest():
        raise ValueError("Discovery reference SHA-256 mismatch")
    return raw,metadata


def build_discovery(screening, *, xetra=None, sec=None, repo_root=None):
    if not isinstance(screening,dict) or screening.get("schema_version")!=1:
        raise ValueError("Original Block B screening contract required")
    rows=screening.get("results")
    if not isinstance(rows,list) or len(rows)!=screening.get("universe_size") or len(rows)>5000:
        raise ValueError("Screening identity universe count inconsistent")
    mode=screening.get("dataset_mode")
    if mode not in (SYNTHETIC, EXTERNAL):
        raise ValueError("Unknown source evidence mode")
    try:
        as_of=date.fromisoformat(screening["as_of"])
    except (TypeError,ValueError,KeyError):
        raise ValueError("Discovery as-of invalid") from None
    ids=set()
    for r in rows:
        if not isinstance(r,dict) or not isinstance(r.get("id"),str) or r["id"] in ids:
            raise ValueError("Missing/duplicate screened identifier")
        ids.add(r["id"])

    if mode==SYNTHETIC and (xetra is not None or sec is not None):
        raise ValueError("Real reference catalogs cannot certify synthetic instrument identities")
    catalogs={}
    matched=set()
    ambiguous=0
    if xetra is not None:
        if not isinstance(xetra,tuple) or len(xetra)!=2 or repo_root is None:
            raise ValueError("Xetra requires original raw and meta source")
        data,meta=_original(*xetra,repo_root=repo_root,cap=20_000_000)
        instruments,manifest=parse_xetra(data,meta,as_of=as_of)
        # Exact venue+currency+ISIN, never symbol fuzzy matching.
        keys=Counter((r["isin"],r["venue"],r["currency"]) for r in instruments)
        for row in rows:
            if row.get("venue")=="XETR":
                key=(row.get("isin"),row.get("venue"),row.get("currency"))
                if keys.get(key,0)==1:
                    matched.add(row["id"])
                if keys.get(key,0)>1:
                    ambiguous+=1
        catalogs["XETRA_T7"]={
            "original_raw_sha256":manifest["source_raw_sha256"],
            "catalog_count":len(instruments),
            "reference_as_of":manifest["as_of"],
            "identities_exactly_matched_to_screening":len(matched),
            "multiple_listing_identity_review_count":ambiguous,
            "by_asset_type":dict(sorted(Counter(r["asset_type"] for r in instruments).items())),
            "prices_present":False,
            "legal_etp_fiscal_classification_certified":False,
        }
    if sec is not None:
        if not isinstance(sec,tuple) or len(sec)!=2 or repo_root is None:
            raise ValueError("SEC needs original raw and metadata source")
        raw,meta=_original(*sec,repo_root=repo_root,cap=8_000_000)
        if meta.get("provider")!="SEC_TICKERS" or meta.get("source_url")!=SEC_TICKERS_URL:
            raise ValueError("SEC original reference provenance invalid")
        from datetime import datetime,timedelta
        try:
            retrieved=datetime.fromisoformat(meta["retrieved_at_utc"].replace("Z","+00:00"))
        except (ValueError,KeyError,AttributeError):
            raise ValueError("SEC acquisition timestamp invalid") from None
        if retrieved.utcoffset()!=timedelta(0) or retrieved.date()>as_of:
            raise ValueError("SEC snapshot retrieved in future/without UTC")
        candidates=parse_sec_tickers(raw)
        mapped=[r for r in candidates if r["venue"] in ("XNYS","XNAS")]
        catalogs["SEC_US_EXCHANGES"]={
            "original_raw_sha256":hashlib.sha256(raw).hexdigest(),
            "catalog_count":len(candidates),
            "supported_venue_listings":len(mapped),
            "exchange_counts":dict(sorted(Counter(x["venue"] for x in mapped).items())),
            "screening_isin_matches_proven":0,
            "SEC_ISIN_mappings_in_this_catalog":0,
            "provenance_url":SEC_TICKERS_URL,
            "prices_present":False,
        }

    if mode==SYNTHETIC and catalogs:
        raise ValueError("Real catalogs cannot certify synthetic asset identities")
    cohort=Counter((r.get("venue","UNKNOWN"),r.get("asset_type","UNKNOWN"))
                   for r in rows)
    covered_venues={x[0] for x in cohort}
    excluded=sum(r.get("market_score") is None for r in rows)
    audit={
        "schema_version":VERSION,
        "as_of":as_of.isoformat(),"dataset_mode":mode,
        "dataset_manifest_sha256":screening["dataset_manifest_sha256"],
        "screening_sha256":_sha(screening),
        "source_screened_universe_count":len(rows),
        "source_ranked_count":screening.get("ranked_count"),
        "market_data_missing_or_incomplete":excluded,
        "screened_venues":sorted(covered_venues),
        "screened_by_venue_and_class":[{"venue":v,"asset_type":t,"count":n}
                                       for (v,t),n in sorted(cohort.items())],
        "reference_catalogs":catalogs,
        "reference_catalog_count":len(catalogs),
        "exact_verified_xetra_reference_matches":len(matched),
        "unresolved_duplicate_listings":ambiguous,
        "SEC_ticker_only_not_ISIN_confirmed":bool(sec),
        "global_representative_universe_certified":False,
        "status":"PARTIAL_TWO_VENUE_DISCOVERY_REFERENCE_NOT_GLOBAL_PRICE_UNIVERSE"
                 if catalogs else "NO_INDEPENDENT_DISCOVERY_REFERENCE_SUPPLIED",
        "not_ranked_from_catalogs":True,"trade_ready":False,
        "limitations":[
            "SEC CIK/ticker/exchange listing lacks official ISIN and cannot supply an equity price, legal class or corporate action.",
            "Xetra T7 listing identifies securities but may include multiple listings per ISIN and never certifies source data rights.",
            "SEC+Xetra do not constitute representative worldwide sector, class or venue price coverage.",
            "Only the screened price bundle supplies ranking; missing historical prices and identity remain explicit.",
        ],
    }
    if excluded!=len(rows)-screening.get("ranked_count",0):
        raise ValueError("Market coverage denominator inconsistent with original screening")
    return audit


def write_discovery(report,output,*,repo_root):
    out=Path(output).resolve()
    root=Path(repo_root).resolve()
    if report["dataset_mode"]!=SYNTHETIC and out.is_relative_to(root) and not out.is_relative_to(root/"data/private"):
        raise ValueError("Real reference catalog evidence must be private inside repo")
    out.mkdir(parents=True,exist_ok=True)
    (out/"DISCOVERY_COVERAGE.json").write_text(
        json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return out
