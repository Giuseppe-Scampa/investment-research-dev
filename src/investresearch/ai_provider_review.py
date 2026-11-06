"""M5/R-009: deterministic multi-provider PUBLIC-only AI critique comparison.

Imported and opt-in free-tier remote responses: reconciliation itself never
invokes APIs. No semantic consensus or citation fact-check by string matching.
Results are review *queues*, not automatically validated financial research.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .ai_counteranalysis import PROVIDERS, MODEL_ID, SOURCE_ID, SHA256, _canonical_bytes

VERSION="r009-multi-provider-reconciliation-v1"
RECORD="r009-counteranalysis-result-v1"


def _sha(value):
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _verify(record):
    if not isinstance(record,dict) or record.get("schema_version")!=RECORD:
        raise ValueError("Expected original R-009 public counteranalysis record")
    if record.get("provider") not in PROVIDERS or not MODEL_ID.fullmatch(str(record.get("model",""))):
        raise ValueError("Unknown AI provider or model")
    billing_by_execution={
        "OPT_IN_LOCAL_OLLAMA":"NO_PAID_REMOTE_API_CALLED_BY_THIS_MODULE",
        "IMPORTED_RESPONSE_NO_NETWORK":"NO_PAID_REMOTE_API_CALLED_BY_THIS_MODULE",
        "OPT_IN_FREE_TIER_REMOTE":"FREE_TIER_OPERATOR_ACKNOWLEDGED_BILLING_NOT_ATTESTED",
    }
    if (record.get("execution") not in billing_by_execution
            or record.get("api_billing_status")!=billing_by_execution.get(record.get("execution"))
            or record.get("result_status")!="AI_UNVERIFIED_COUNTERANALYSIS_HUMAN_REVIEW_REQUIRED"
            or record.get("citation_status")!="KNOWN_SOURCE_IDS_ONLY_NOT_FACT_CHECKED"
            or record.get("rank_or_tax_authorization") is not False):
        raise ValueError("Imported AI evidence claims unverified paid/provider/trade authority")
    if record["execution"]=="OPT_IN_LOCAL_OLLAMA" and record["provider"]!="ollama-local":
        raise ValueError("Only local Ollama may have actually been invoked in these records")
    if record["execution"]=="OPT_IN_FREE_TIER_REMOTE":
        from .ai_remote_free import validate_free_model
        validate_free_model(record["provider"], record["model"])
    try:
        cutoff=date.fromisoformat(record["research_as_of"])
    except (KeyError,ValueError,TypeError):
        raise ValueError("AI research as-of invalid") from None
    for name in ("input_sha256","response_sha256"):
        if not isinstance(record.get(name),str) or not SHA256.fullmatch(record[name]):
            raise ValueError("Missing original AI input/output SHA256")
    sources=record.get("sources")
    if not isinstance(sources,list) or not 1<=len(sources)<=8:
        raise ValueError("Original AI source register missing")
    ids=set()
    for item in sources:
        if not isinstance(item,dict):
            raise ValueError("Malformed public source")
        sid=item.get("source_id")
        if not isinstance(sid,str) or not SOURCE_ID.fullmatch(sid) or sid in ids:
            raise ValueError("Missing or duplicate R-009 source ID")
        ids.add(sid)
        u=urlsplit(item.get("url",""))
        if (u.scheme!="https" or not u.hostname or u.username or u.password
                or u.fragment or u.hostname.lower() in {"localhost","127.0.0.1","::1"}):
            raise ValueError("AI source URL invalid")
        try:
            if date.fromisoformat(item["published_date"])>cutoff:
                raise ValueError("AI citations dated after research snapshot")
        except (TypeError,KeyError):
            raise ValueError("AI source publication date invalid") from None
        sha=item.get("sha256_as_supplied_not_authenticated")
        if sha is not None and (not isinstance(sha,str) or not SHA256.fullmatch(sha)):
            raise ValueError("AI source snapshot digest invalid")
    claims=record.get("counterarguments")
    doubts=record.get("uncertainties")
    summary=record.get("summary")
    if (not isinstance(summary,str) or not summary.strip() or len(summary)>2500
            or not isinstance(claims,list) or len(claims)>12
            or not isinstance(doubts,list) or len(doubts)>12):
        raise ValueError("Oversized or missing AI counterarguments")
    for item in claims:
        if (not isinstance(item,dict) or set(item)!={"claim","source_ids"}
                or not isinstance(item["claim"],str) or not 0<len(item["claim"])<=1500
                or not isinstance(item["source_ids"],list) or not item["source_ids"]
                or len(set(item["source_ids"]))!=len(item["source_ids"])
                or not set(item["source_ids"]).issubset(ids)):
            raise ValueError("Citation IDs do not support an imported public record")
    if not all(isinstance(x,str) and 0<len(x)<=1000 for x in doubts):
        raise ValueError("Invalid AI uncertainty statements")
    response={"summary":summary,"counterarguments":claims,"uncertainties":doubts}
    if record["response_sha256"]!=_sha(response):
        raise ValueError("AI response was altered after its original digest")
    return cutoff


def reconcile(records):
    if not isinstance(records,list) or not 2<=len(records)<=4:
        raise ValueError("Compare exactly 2–4 distinct free/local provider records")
    providers=set()
    asof, original=None,None
    refs={}
    grouped=defaultdict(list)
    source_registry=None
    for r in records:
        cutoff=_verify(r)
        if r["provider"] in providers:
            raise ValueError("Repeated provider is not a second independent model")
        providers.add(r["provider"])
        if asof is None:
            asof=cutoff
            original=r["input_sha256"]
            source_registry={s["source_id"]:(s["url"],s["published_date"],
                s.get("sha256_as_supplied_not_authenticated")) for s in r["sources"]}
        elif cutoff!=asof or r["input_sha256"]!=original:
            raise ValueError("Different source snapshot/date; cannot compare AI providers")
        else:
            current={s["source_id"]:(s["url"],s["published_date"],
                s.get("sha256_as_supplied_not_authenticated")) for s in r["sources"]}
            if current!=source_registry:
                raise ValueError("AI providers did not use identical public evidence registers")
        refs[r["provider"]]={
            "model":r["model"],"record_sha256":_sha(r),
            "counterarguments":len(r["counterarguments"]),
            "uncertainties":len(r["uncertainties"]),
        }
        for claim in r["counterarguments"]:
            # Exact normalized text = exact text match only, NEVER semantic consensus.
            text=" ".join(claim["claim"].split()).casefold()
            key=hashlib.sha256(text.encode("utf-8")).hexdigest()
            grouped[key].append({
                "provider":r["provider"], "claim":claim["claim"],
                "source_ids":sorted(claim["source_ids"]),
            })
    queue=[]
    for key in sorted(grouped):
        items=sorted(grouped[key],key=lambda x:x["provider"])
        queue.append({
            "literal_text_sha256":key,
            "literal_match_providers":[x["provider"] for x in items],
            "provider_count":len(items),
            "claims":items,
            "exact_text_overlap_only":len(items)>1,
            "independently_fact_checked":False,
            "required_human_action":"Check original issuer/source documents and conflicting claims manually",
        })
    return {
        "schema_version":VERSION,
        "as_of":asof.isoformat(),"public_research_input_sha256":original,
        "provider_count":len(refs),
        "providers":dict(sorted(refs.items())),
        "unique_literal_claims":len(queue),
        "literal_overlaps":sum(row["exact_text_overlap_only"] for row in queue),
        "human_fact_check_queue":queue,
        "semantic_agreement_verified":False,
        "source_documents_independently_authenticated":False,
        "citation_claim_support_fact_checked":False,
        "billing_claim":"NO_REMOTE_OR_PAID_PROVIDER_CALLED_BY_RECONCILIATION",
        "trade_ready":False,"rank_or_tax_authorization":False,
        "status":"MULTI_PROVIDER_PUBLIC_COUNTERANALYSIS_UNVERIFIED_REVIEW_REQUIRED",
    }


def write_reconciliation(result, output, *, repo_root):
    root=Path(repo_root).resolve()
    out=Path(output).resolve()
    if out.is_relative_to(root) and not out.is_relative_to(root/"data/private"):
        raise ValueError("AI source/claim material must be in ignored private research directory")
    if out.exists():
        raise ValueError("No overwrite of human-review counteranalysis evidence")
    out.mkdir(parents=True)
    (out/"AI_PROVIDER_RECONCILIATION.json").write_text(
        json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    lines=["# Independent AI criticism — not independently fact checked","",
           f"Research as-of: {result['as_of']}",
           f"Providers: {result['provider_count']}, literal text overlaps: {result['literal_overlaps']}",
           "","All arguments require human check against ORIGINAL dated source documents.",
           "Exact same wording does not establish true or independently substantiated claims.",
           ""]
    for entry in result["human_fact_check_queue"]:
        lines.append("- "+html.escape(entry["claims"][0]["claim"])+" [providers: "+
                     ", ".join(entry["literal_match_providers"])+"]")
    (out/"AI_PROVIDER_RECONCILIATION.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return out
