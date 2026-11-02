"""Optional ESEF live compatibility check against an official issuer ZIP.

Public, one-off, no secrets or uploaded raw documents. A network or parser
failure is explicitly reported and is NOT proof of correct financial facts.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from investresearch.research_eu_filings import MODE, MAX_DOCUMENT_BYTES, audit_eu_reports

EDISON_URL = ('https://www.edison.it/sites/default/files/documents/'
              '529900ws2e20ba5j4l49-2025-12-31-1-it_1.zip')
EDISON_LEI = '529900WS2E20BA5J4L49'
EDISON_SUFFIX = '529900ws2e20ba5j4l49-2025-12-31-1-it.xhtml'
# Immutable source captured from the issuer's official 2025 package in the
# initial 2026-11-02 live run. Changed bytes require a fresh document review.
EDISON_2025_SHA256 = '4ab61d8a4a959801cc487711ae0850a524b531f7aacf311ecf09ad7131711232'

# These are reference figures from the issuer's FY2025 PDF, not expected
# iXBRL tag equivalents, and no automatic promotion to verified facts occurs.
PDF_CONTROL_EUR = {
    'REVENUE': {17_739_000_000, 17_986_000_000},
    'PROFIT_LOSS': {270_000_000},
    'PROFIT_PARENT': {240_000_000},
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Issuer redirected download: new endpoint requires review')


def fetch_official_zip() -> bytes:
    req = Request(EDISON_URL, headers={
        'User-Agent': 'InvestmentResearchDev/0.5 (+public ESEF research verification)',
        'Accept': 'application/zip,application/octet-stream',
    })
    try:
        with build_opener(_NoRedirect()).open(req, timeout=25) as response:
            payload = response.read(MAX_DOCUMENT_BYTES + 1)
    except HTTPError as exc:
        raise RuntimeError(f'EDISON_ESEF_DOWNLOAD_HTTP_{exc.code}') from None
    except URLError:
        raise RuntimeError('EDISON_ESEF_DOWNLOAD_NETWORK_UNAVAILABLE') from None
    if not 0 < len(payload) <= MAX_DOCUMENT_BYTES or not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError('Issuer ESEF response not a valid bounded ZIP')
    return payload


def select_consolidated_xhtml(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [m.filename for m in archive.infolist()
                   if m.filename.lower().endswith(EDISON_SUFFIX)
                   and '/reports/' in '/' + m.filename.lower()]
    if len(matches) != 1:
        raise ValueError(f'Issuer ESEF archive expected one consolidated XHTML member; got {len(matches)}')
    return matches[0]



def inspect_supported_fact_coverage(payload: bytes, member: str) -> dict:
    """Count real iXBRL metadata only, never log the source XHTML or amounts."""
    from collections import Counter
    from investresearch.research_eu_filings import _esef_report_xhtml
    from investresearch.research_ixbrl import (
        _parse_tree, _contexts, _units, _qualified,
        IFRS_NS, CONCEPTS, IXBRL, TRANSFORMS,
    )
    xhtml = _esef_report_xhtml(payload, 'ESEF_ZIP', member)
    root, prefixes = _parse_tree(xhtml)
    contexts, _ = _contexts(root, date(2025, 12, 31))
    units = _units(root, prefixes)
    all_concepts = Counter()
    eligible_formats = Counter()
    valid_formats = Counter()
    eligible = 0
    for node in root.iter(f'{{{IXBRL}}}nonFraction'):
        namespace, concept = _qualified(node.get('name'), prefixes)
        if not IFRS_NS.fullmatch(namespace) or concept not in CONCEPTS:
            continue
        all_concepts[concept] += 1
        if node.get('contextRef') not in contexts or node.get('unitRef') not in units:
            continue
        eligible += 1
        fmt = node.get('format', 'UNFORMATTED')
        if fmt == 'UNFORMATTED':
            key = 'UNFORMATTED'
            valid_formats[key] += 1
        else:
            ns, name = _qualified(fmt, prefixes)
            # Explicit URI/name, not any value or source content.
            key = ns[:120] + ':' + name[:60]
            if name in TRANSFORMS.get(ns, {}):
                valid_formats[key] += 1
        eligible_formats[key] += 1
    return {
        'recognized_ifrs_concepts_before_context_filter': dict(sorted(all_concepts.items())),
        'supported_annual_undimensioned_contexts': len(contexts),
        'supported_eur_units': len(units),
        'eligible_ifrs_facts_before_numeric_conversion': eligible,
        'eligible_numeric_transforms_seen': dict(sorted(eligible_formats.items())),
        'eligible_supported_transforms': dict(sorted(valid_formats.items())),
    }


def verify_official_package(payload: bytes, as_of: date) -> dict:
    """Audit exact ESEF source and compare only supported IFRS candidates.

    All results remain UNVERIFIED. A PDF reference match is not XBRL validation
    or a legally sufficient issuer financial statement certification.
    """
    if as_of < date(2026, 2, 26):
        raise ValueError('ESEF test cannot predate issuer publication')
    if not 0 < len(payload) <= MAX_DOCUMENT_BYTES:
        raise ValueError('Invalid ESEF archive size')
    member = select_consolidated_xhtml(payload)
    with TemporaryDirectory(prefix='edison-esef-') as folder:
        base = Path(folder)
        (base / 'edison-2025.zip').write_bytes(payload)
        spec = {'mode': MODE, 'as_of': as_of.isoformat(), 'documents': [{
            'id': 'EDISON_FY2025_CONSOLIDATED',
            'issuer_name': 'Edison SpA',
            'format': 'ESEF_ZIP',
            'source_type': 'ISSUER_INVESTOR_RELATIONS',
            'relative_path': 'edison-2025.zip',
            'xhtml_member': member,
            'sha256': hashlib.sha256(payload).hexdigest(),
            'source_url': EDISON_URL,
            'published_date': '2026-02-26',
            'fiscal_year_end': '2025-12-31',
            'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
            'lei': EDISON_LEI,
        }]}
        report = audit_eu_reports(spec, base, extract_ifrs=True)
    item = report['results'][0]
    ix = item['ixbrl']
    diagnostics = inspect_supported_fact_coverage(payload, member)
    from decimal import Decimal
    comparisons=[]
    for fact in ix['facts']:
        metric = fact['metric']
        if metric not in PDF_CONTROL_EUR:
            continue
        amount=Decimal(fact['value_eur'])
        comparisons.append({
            'metric': metric, 'concept': fact['concept'],
            'value_eur': fact['value_eur'],
            'pdf_amount_matches': amount in PDF_CONTROL_EUR[metric],
        })
    return {
        'status': 'LIVE_ESEF_CANDIDATES_UNVERIFIED_NOT_RANKED',
        'document_sha256': item['document_sha256'],
        'selected_member': member,
        'candidate_count': ix['candidate_count'],
        'conflicting_metrics': ix.get('conflicting_metrics', []),
        'rejection_counts': ix['rejected_fact_reasons'],
        'diagnostics': diagnostics,
        'pdf_reference_compared_count': len(comparisons),
        'pdf_reference_numeric_matches': sum(x['pdf_amount_matches'] for x in comparisons),
        'pdf_comparison_candidates': comparisons,
        'accounting_facts_verified': report['accounting_facts_verified'],
        'market_ranking_count': report['market_ranking_count'],
    }



def validate_live_reference_controls(result: dict) -> tuple[bool, str]:
    """Strict three-metric *numeric* cross-check, not a XBRL audit certificate."""
    if result.get('document_sha256') != EDISON_2025_SHA256:
        return False, 'OFFICIAL_ESEF_ZIP_BYTES_CHANGED_REQUIRE_REVIEW'
    if result.get('accounting_facts_verified') != 0 or result.get('market_ranking_count') != 0:
        return False, 'UNEXPECTED_PROMOTION_TO_VERIFIED_OR_RANKED_STATUS'
    if result.get('conflicting_metrics'):
        return False, 'CONFLICTING_IFRS_METRIC_FACTS_REQUIRE_MANUAL_REVIEW'
    comparisons = result.get('pdf_comparison_candidates', [])
    expected = {
        ('REVENUE', 'Revenue', '17739000000'),
        ('PROFIT_LOSS', 'ProfitLoss', '270000000'),
        ('PROFIT_PARENT', 'ProfitLossAttributableToOwnersOfParent', '240000000'),
    }
    observed = {(c.get('metric'),c.get('concept'),c.get('value_eur'))
                for c in comparisons if c.get('pdf_amount_matches') is True}
    if not expected.issubset(observed):
        return False, 'OFFICIAL_PDF_REFERENCE_VALUES_INCOMPLETE_OR_DIFFERENT'
    if any(c.get('pdf_amount_matches') is not True for c in comparisons):
        return False, 'ADDITIONAL_PDF_REFERENCE_CONFLICT_REQUIRES_REVIEW'
    if len(comparisons) != result.get('candidate_count'):
        return False, 'UNMAPPED_OR_UNMATCHED_IFRS_CANDIDATES_REQUIRE_REVIEW'
    return True, 'THREE_NUMERIC_PDF_REFERENCES_MATCH_IN_ESEF_REVIEW_REQUIRED'


def main():
    try:
        result = verify_official_package(fetch_official_zip(), date.today())
    except Exception as exc:
        # No raw bytes or local cache paths, no tokens/secrets in the log.
        print('LIVE ESEF NOT VALIDATED:', type(exc).__name__, str(exc)[:180], file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    if not result['candidate_count']:
        print('LIVE ESEF INCOMPLETE: zero extractable candidates, review transformation and contexts', file=sys.stderr)
        return 2
    accepted, reason = validate_live_reference_controls(result)
    print('LIVE ESEF RECONCILIATION:', reason)
    if not accepted:
        return 2
    print('LIVE ESEF THREE-METRIC NUMERIC CHECK COMPLETED: human audit still required')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
