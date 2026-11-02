"""Optional live test of Prysmian's official FY2025 ESEF package.

No secrets, issuer raw files, or market histories are uploaded. Results are
review candidates, never verified accounting facts or investment rankings.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from investresearch.research_eu_filings import MODE, MAX_DOCUMENT_BYTES, audit_eu_reports

ISSUER_URL = ('https://www.prysmian.com/sites/www.prysmian.com/files/media/'
              'documents/529900X0H1IO3RS1A464-2025-12-31-1-en.zip')
ISSUER_LEI = '529900X0H1IO3RS1A464'
EXPECTED_REPORT_NAME = '529900x0h1io3rs1a464-2025-12-31-1-en.xhtml'
# Reference values are from issuer's public FY2025 investor disclosures, NOT
# an independent line-by-line inspection of the IFRS consolidated statements.
# Figures are in millions of EUR; a match is only a numeric coverage signal.
INVESTOR_REFERENCE = {
    'REVENUE': Decimal('19650000000'),
    'PROFIT_LOSS': Decimal('1270000000'),
    'PROFIT_PARENT': Decimal('1270000000'),
}
MAX_DOWNLOAD = MAX_DOCUMENT_BYTES


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Issuer download redirected: endpoint needs review')


def fetch_official_zip() -> bytes:
    req = Request(ISSUER_URL, headers={
        'User-Agent': 'InvestmentResearchDev/0.6 (public ESEF compatibility check)',
        'Accept': 'application/zip,application/octet-stream',
    })
    try:
        with build_opener(NoRedirect()).open(req, timeout=30) as response:
            if response.geturl() != ISSUER_URL:
                raise RuntimeError('Issuer returned unexpected final download URL')
            payload = response.read(MAX_DOWNLOAD + 1)
    except HTTPError as exc:
        raise RuntimeError(f'PRYSMIAN_ESEF_HTTP_{exc.code}') from None
    except URLError:
        raise RuntimeError('PRYSMIAN_ESEF_NETWORK_UNAVAILABLE') from None
    if not 0 < len(payload) <= MAX_DOWNLOAD or not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError('Issuer ESEF payload must be a bounded ZIP')
    return payload


def select_consolidated_xhtml(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [
            m.filename for m in archive.infolist()
            if not m.is_dir()
            and m.filename.lower().endswith(EXPECTED_REPORT_NAME)
            and '/reports/' in ('/' + m.filename.lower())
        ]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one consolidated ESEF XHTML, got {len(matches)}')
    return matches[0]


def verify_official_package(payload: bytes, as_of: date) -> dict:
    if as_of < date(2026, 3, 13):
        raise ValueError('Report could not have been published by as_of')
    if not 0 < len(payload) <= MAX_DOCUMENT_BYTES:
        raise ValueError('Issuer ESEF archive exceeds size limit')
    sha256 = hashlib.sha256(payload).hexdigest()
    member = select_consolidated_xhtml(payload)
    with TemporaryDirectory(prefix='prysmian-esef-') as temp:
        folder = Path(temp)
        (folder/'prysmian-2025.zip').write_bytes(payload)
        spec = {'mode': MODE, 'as_of': as_of.isoformat(), 'documents':[{
            'id':'PRYSMIAN_FY2025_CONSOLIDATED',
            'issuer_name':'Prysmian S.p.A.',
            'format':'ESEF_ZIP',
            'source_type':'ISSUER_INVESTOR_RELATIONS',
            'relative_path':'prysmian-2025.zip',
            'xhtml_member':member,
            'sha256':sha256,
            'source_url':ISSUER_URL,
            'published_date':'2026-03-13',
            'fiscal_year_end':'2025-12-31',
            'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
            'lei':ISSUER_LEI,
        }]}
        report = audit_eu_reports(spec, folder, extract_ifrs=True)
    if report['document_count'] != 1 or report['accounting_facts_verified'] != 0 or report['market_ranking_count'] != 0:
        raise ValueError('Unexpected promotion from review candidates to verified financial facts')
    ix = report['results'][0]['ixbrl']
    facts = ix.get('facts', [])
    matches=[]
    for fact in facts:
        metric = fact['metric']
        try:
            value = Decimal(fact['value_eur'])
        except (KeyError, ValueError):
            raise ValueError('Parser returned invalid candidate value') from None
        target = INVESTOR_REFERENCE.get(metric)
        # The reference is in EUR millions. A 0.5m tolerance matches rounding
        # of an official published whole-million figure, not taxonomy identity.
        matches.append({'metric':metric, 'concept':fact['concept'],
                        'value_eur':str(value),
                        'matches_rounded_investor_reference':(
                            target is not None and abs(value-target) <= Decimal('500000'))})
    return {
        'mode':'PRYSMIAN_FY2025_ESEF_DIAGNOSTIC_NOT_AUDITED',
        'source_url':ISSUER_URL,
        'sha256':sha256,
        'selected_member':member,
        'candidate_count':ix['candidate_count'],
        'numeric_reference_matches':sum(1 for m in matches if m['matches_rounded_investor_reference']),
        'metrics_found':sorted(set(f['metric'] for f in facts)),
        'conflicting_metrics':ix.get('conflicting_metrics', []),
        'rejected_fact_reasons':ix.get('rejected_fact_reasons', {}),
        'candidates':matches,
        'accounting_facts_verified':0,
        'market_ranking_count':0,
        'limitations':[
            'The 2025 investor highlights are NOT a substitute for line-by-line PDF reconciliation.',
            'The archive SHA256 is not yet pinned; publication date is an issuer-page declaration.',
            'No IFRS extensions, sector-specific revenue, or audit certification is inferred.',
            'No market-data licensing, executable prices, or investment ranking is established.',
        ],
    }


def validate_compatibility(result: dict) -> tuple[bool, str]:
    if result.get('accounting_facts_verified') != 0 or result.get('market_ranking_count') != 0:
        return False, 'UNEXPECTED_AUTOMATIC_FACT_OR_RANK_PROMOTION'
    if result.get('candidate_count', 0) < 1:
        return False, 'ZERO_IFRS_CANDIDATES'
    if result.get('conflicting_metrics'):
        return False, 'CONFLICTING_METRIC_CANDIDATES_REQUIRE_REVIEW'
    if not result.get('numeric_reference_matches'):
        return False, 'NO_2025_INVESTOR_REFERENCE_NUMERIC_MATCH'
    return True, 'PRELIMINARY_IFRS_COMPATIBILITY_ONLY_NOT_PDF_VALIDATION'


def main() -> int:
    try:
        report = verify_official_package(fetch_official_zip(),date.today())
    except Exception as exc:
        # Do not print response bodies, raw XHTML, or local paths.
        print('PRYSMIAN LIVE ESEF INCOMPLETE:',type(exc).__name__,str(exc)[:160],file=sys.stderr)
        return 1
    print(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False))
    okay, message = validate_compatibility(report)
    print('PRYSMIAN ESEF PROBE:',message)
    return 0 if okay else 2


if __name__ == '__main__':
    raise SystemExit(main())
