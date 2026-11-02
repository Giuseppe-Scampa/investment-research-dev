"""Offline European annual-report document register (ESEF/PDF).

This verifies bytes and publication dates, not accounting facts, audit opinions,
issuer identity, licenses or the legal authenticity of a declared source URL.
Raw documents are NEVER copied to the report or the GitHub artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import re
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from xml.etree import ElementTree

from .quality import valid_isin

MAX_DOCUMENT_BYTES = 50_000_000
MAX_ZIP_UNCOMPRESSED = 200_000_000
FORMATS = {'ESEF_XHTML', 'ESEF_ZIP', 'ANNUAL_PDF'}
SOURCE_CATEGORIES = {'ISSUER_INVESTOR_RELATIONS', 'OFFICIALLY_APPOINTED_MECHANISM',
                     'EXCHANGE_DISCLOSURE'}
MODE = 'EU_ANNUAL_REPORT_EVIDENCE_NOT_FINANCIAL_FACTS_OR_RANKING'


def _https_url(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError('A declared HTTPS document source is required')
    parsed = urlsplit(text)
    host = parsed.hostname
    if (parsed.scheme != 'https' or not host or parsed.username or parsed.password
            or parsed.fragment or host.lower() == 'localhost' or host.lower().endswith('.local')):
        raise ValueError('Unsafe or missing HTTPS document source')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('An HTTPS public hostname, not an IP address, is required')
    return text


def _local_document(root: Path, relative_path: str) -> Path:
    """Only open ordinary, nonsymlink files underneath the explicit local root."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError('Relative document path required')
    rel = Path(relative_path)
    if rel.is_absolute() or '..' in rel.parts or rel.name in ('', '.', '..'):
        raise ValueError('Document path traversal or absolute path refused')
    root = Path(root).resolve(strict=True)
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Document symlink refused')
    if not current.resolve().is_relative_to(root) or not current.is_file():
        raise ValueError('Document must be a local file under the configured root')
    if not 0 < current.stat().st_size <= MAX_DOCUMENT_BYTES:
        raise ValueError('Document exceeds supported size or is empty')
    return current


def _verify_format(payload: bytes, document_format: str):
    if document_format == 'ANNUAL_PDF':
        if not payload.startswith(b'%PDF-'):
            raise ValueError('Document is not a PDF')
        return
    if document_format == 'ESEF_XHTML':
        try:
            node = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise ValueError('ESEF XHTML is not well-formed XML') from exc
        if node.tag.split('}')[-1].lower() != 'html':
            raise ValueError('ESEF XHTML must have an html root')
        return
    if document_format != 'ESEF_ZIP':
        raise ValueError('Unsupported European annual-report format')
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.infolist()
            if not names or len(names) > 1000:
                raise ValueError('Empty or oversized ESEF archive listing')
            expanded = 0
            has_xhtml = False
            for member in names:
                p = PurePosixPath(member.filename)
                if (p.is_absolute() or '..' in p.parts or '\\' in member.filename
                        or member.flag_bits & 1 or (member.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('Unsafe ESEF archive entry')
                expanded += member.file_size
                if expanded > MAX_ZIP_UNCOMPRESSED or (member.file_size > 2_000_000 and
                    member.file_size > 200 * max(1, member.compress_size)):
                    raise ValueError('Oversized or highly compressed ESEF archive')
                has_xhtml |= p.suffix.lower() in ('.xhtml', '.html') and not member.is_dir()
            if not has_xhtml:
                raise ValueError('No XHTML report in ESEF ZIP')
    except zipfile.BadZipFile as exc:
        raise ValueError('Invalid ESEF ZIP') from exc


def audit_eu_reports(spec: dict, root: Path) -> dict:
    """Fail closed on bogus provenance, paths, formats and look-ahead.

    `published_date` is an input assertion, not independently authenticated.
    Documents and sensitive local paths are never serialized into results.
    """
    if not isinstance(spec, dict) or spec.get('mode') != MODE:
        raise ValueError('Unexpected European evidence specification mode')
    as_of = date.fromisoformat(spec['as_of'])
    if as_of > datetime.now(timezone.utc).date():
        raise ValueError('Future European evidence cutoff not allowed')
    documents = spec.get('documents')
    if not isinstance(documents, list) or not 1 <= len(documents) <= 100:
        raise ValueError('Require 1-100 explicitly selected European report documents')
    seen = set()
    results = []
    for doc in documents:
        if not isinstance(doc, dict):
            raise ValueError('Document metadata must be an object')
        uid = doc.get('id')
        if not isinstance(uid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', uid) or uid in seen:
            raise ValueError('Invalid or duplicate document ID')
        seen.add(uid)
        issuer = doc.get('issuer_name')
        if not isinstance(issuer, str) or not issuer.strip() or len(issuer) > 200:
            raise ValueError('Issuer name required')
        isin = doc.get('isin', '')
        if isin and not valid_isin(isin):
            raise ValueError('Invalid issuer ISIN')
        fmt = doc.get('format')
        if fmt not in FORMATS:
            raise ValueError('Unsupported European annual-report format')
        source_type = doc.get('source_type')
        if source_type not in SOURCE_CATEGORIES:
            raise ValueError('Unrecognized disclosure source type')
        url = _https_url(doc.get('source_url'))
        published = date.fromisoformat(doc['published_date'])
        fiscal_end = date.fromisoformat(doc['fiscal_year_end'])
        retrieved = datetime.fromisoformat(doc['retrieved_at_utc'].replace('Z', '+00:00'))
        if retrieved.tzinfo is None or retrieved.utcoffset() is None:
            raise ValueError('Collection timestamp must include an offset')
        retrieved_date = retrieved.astimezone(timezone.utc).date()
        if fiscal_end > published or published > as_of or retrieved_date > as_of:
            raise ValueError('Future or inconsistent publication/collection as-of cutoff')
        if retrieved_date < published:
            raise ValueError('Document retrieved before declared publication')
        sha = doc.get('sha256')
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('A complete lowercase document SHA-256 is required')
        local = _local_document(root, doc.get('relative_path'))
        payload = local.read_bytes()
        if hashlib.sha256(payload).hexdigest() != sha:
            raise ValueError('European annual report checksum mismatch')
        _verify_format(payload, fmt)
        results.append({
            'id': uid, 'issuer_name': issuer.strip(), 'isin': isin,
            'fiscal_year_end': fiscal_end.isoformat(),
            'published_date_declared': published.isoformat(),
            'retrieved_date_utc': retrieved_date.isoformat(),
            'format': fmt, 'source_type_declared': source_type,
            'source_url_declared': url, 'document_sha256': sha,
            'status': 'DOCUMENT_HASH_FORMAT_VALID_SOURCE_AND_ACCOUNTING_NOT_VERIFIED',
            'fundamental_score': None, 'market_score': None,
        })
    results.sort(key=lambda r: (r['issuer_name'].casefold(),r['id']))
    return {
        'mode': MODE, 'as_of': as_of.isoformat(), 'document_count': len(results),
        'esef_documents': sum(r['format'].startswith('ESEF_') for r in results),
        'accounting_facts_verified': 0, 'market_ranking_count': 0,
        'results': results,
        'limitations': [
            'Only local document checksums, container formats, and declared dates are validated.',
            'The engine has not independently authenticated the issuer, source URL or publication date.',
            'No XBRL taxonomy/context/unit extraction or cross-issuer IFRS comparability has been performed.',
            'No raw report bytes or local file paths are included in the report.',
            'No market data, tax classification, predictions or trade instructions are produced.',
        ],
    }


def write_eu_report(report: dict, output: Path) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'EU_REPORT_COVERAGE.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    fields = ['id','issuer_name','isin','fiscal_year_end','published_date_declared','format',
              'source_type_declared','source_url_declared','document_sha256','status']
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows([{f:r[f] for f in fields} for r in report['results']])
    (output / 'EU_REPORT_COVERAGE.csv').write_text(buf.getvalue(), encoding='utf-8')
    lines = ['# European issuer annual-report document coverage', '',
             f"- **As-of:** {report['as_of']}",
             f"- **Documents:** {report['document_count']} ({report['esef_documents']} ESEF)",
             '- **Verified numerical fundamentals:** 0 · **Ranked market instruments:** 0', '',
             '> Byte integrity and reported dates are not issuer authentication or accounting verification.', '',
             '## Documents', '', '| Issuer | Report type | Period end | Status |',
             '|---|---|---|---|']
    for row in report['results']:
        esc = lambda v: str(v).replace('|','\\|').replace('\n',' ')
        lines.append(f"| {esc(row['issuer_name'])} | {row['format']} | {row['fiscal_year_end']} | {row['status']} |")
    lines.extend(['','## Limitations'] + ['- ' + x for x in report['limitations']])
    (output / 'EU_REPORT_COVERAGE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return output
