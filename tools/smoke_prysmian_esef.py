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
# Immutable issuer package observed on 2026-11-02 GitHub runner. Changed ZIP
# bytes must never silently be treated as the same financial statement.
PRYSMIAN_FY2025_SHA256 = '75bd4db98fcf84a4cb51330fc0b6c6745fc2fa6a82cf89ecbbea739a2c9c0737'
# Exact controls from Prysmian's own 26 February 2026 consolidated income
# statement, page 12 of the official FY2025 results PDF. These are four
# DIFFERENT concepts, not competing guesses for the same metric.
OFFICIAL_INCOME_STATEMENT_PDF = (
    'https://www.prysmian.com/sites/www.prysmian.com/files/media/documents/'
    'investors/CS_Prysmian_FY25_26022026.pdf'
)
PDF_REFERENCE_BY_CONCEPT = {
    'RevenueFromContractsWithCustomers': Decimal('19650000000'),  # Ricavi
    'Revenue': Decimal('20348000000'),  # Totale ricavi e proventi
    'ProfitLoss': Decimal('1294000000'),  # Risultato netto consolidato
    'ProfitLossAttributableToOwnersOfParent': Decimal('1270000000'),  # Gruppo
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
        target = PDF_REFERENCE_BY_CONCEPT.get(fact['concept'])
        # The official PDF is expressed in rounded EUR millions. A 0.5m
        # tolerance covers rounding only, not semantic comparability.
        matches.append({'metric':metric, 'concept':fact['concept'],
                        'value_eur':str(value),
                        'matches_rounded_pdf_concept':(
                            target is not None and abs(value-target) <= Decimal('500000'))})
    return {
        'mode':'PRYSMIAN_FY2025_ESEF_DIAGNOSTIC_NOT_AUDITED',
        'source_url':ISSUER_URL,
        'sha256':sha256,
        'selected_member':member,
        'candidate_count':ix['candidate_count'],
        'numeric_reference_matches':sum(1 for m in matches if m['matches_rounded_pdf_concept']),
        'pdf_reference_url': OFFICIAL_INCOME_STATEMENT_PDF,
        'metrics_found':sorted(set(f['metric'] for f in facts)),
        'conflicting_metrics':ix.get('conflicting_metrics', []),
        'rejected_fact_reasons':ix.get('rejected_fact_reasons', {}),
        'candidates':matches,
        'accounting_facts_verified':0,
        'market_ranking_count':0,
        'limitations':[
            'Numeric agreement is with the official FY2025 consolidated income statement PDF, not a full XBRL audit.',
            'Revenue and RevenueFromContractsWithCustomers are intentionally different concepts; no score may pick one automatically.',
            'The report publication date is an issuer-page declaration, not an independently authenticated timestamp.',
            'No IFRS extensions, sector-specific revenue, or audit certification is inferred.',
            'No market-data licensing, executable prices, or investment ranking is established.',
        ],
    }


def validate_compatibility(result: dict) -> tuple[bool, str]:
    """Pin exact issuer bytes and reconcile ALL supported candidates by concept.

    Preserve REVENUE semantic ambiguity for manual human selection. A numeric
    match does not certify XBRL validity, issuer audit or suitability to score.
    """
    if result.get('sha256') != PRYSMIAN_FY2025_SHA256:
        return False, 'PRYSMIAN_OFFICIAL_ZIP_CHANGED_REQUIRES_REVIEW'
    if result.get('accounting_facts_verified') != 0 or result.get('market_ranking_count') != 0:
        return False, 'UNEXPECTED_AUTOMATIC_FACT_OR_RANK_PROMOTION'
    expected = set(PDF_REFERENCE_BY_CONCEPT)
    found = result.get('candidates', [])
    if result.get('candidate_count') != len(found) or len(found) < len(expected):
        return False, 'INCOMPLETE_IFRS_CANDIDATES'
    observed = {r.get('concept') for r in found}
    if observed != expected:
        return False, 'IFRS_CONCEPT_COVERAGE_CHANGED_REQUIRE_REVIEW'
    if any(r.get('matches_rounded_pdf_concept') is not True for r in found):
        return False, 'OFFICIAL_PDF_AMOUNT_MISMATCH'
    if result.get('conflicting_metrics') != ['REVENUE']:
        return False, 'REVENUE_CONCEPT_AMBIGUITY_CHANGED_REQUIRE_REVIEW'
    return True, 'FOUR_DISTINCT_IFRS_CONCEPTS_MATCH_OFFICIAL_PDF_NUMERICALLY_HUMAN_REVIEW_STILL_REQUIRED'


def main() -> int:
    try:
        payload = fetch_official_zip()
        member = select_consolidated_xhtml(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            info = archive.getinfo(member)
            print('PRYSMIAN ESEF ARCHIVE METADATA:',
                  'zip_bytes=',len(payload),
                  'selected_xhtml_declared_bytes=',info.file_size,
                  'selected_xhtml_compressed_bytes=',info.compress_size,
                  flush=True)
        report = verify_official_package(payload,date.today())
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
