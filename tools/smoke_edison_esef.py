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
        'pdf_reference_compared_count': len(comparisons),
        'pdf_reference_numeric_matches': sum(x['pdf_amount_matches'] for x in comparisons),
        'pdf_comparison_candidates': comparisons,
        'accounting_facts_verified': report['accounting_facts_verified'],
        'market_ranking_count': report['market_ranking_count'],
    }


def main():
    try:
        result = verify_official_package(fetch_official_zip(), date.today())
    except Exception as exc:
        # No raw bytes or local cache paths, no tokens/secrets in the log.
        print('LIVE ESEF NOT VALIDATED:', type(exc).__name__, str(exc)[:180], file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    print('LIVE ESEF AUDIT COMPLETED: candidates only, no certified financials')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
