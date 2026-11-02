"""Conservative offline Inline XBRL IFRS candidate extraction; NOT an XBRL validator.

All outputs are provisional accounting candidates for human comparison with an
issuer's audited statements. No extension taxonomy anchoring, calculation
linkbases, transformations outside a tiny audited allowlist or numeric scores.
"""
from __future__ import annotations

import io
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from defusedxml import ElementTree as SafeET

MAX_XHTML_BYTES = 32_000_000
MAX_XML_ELEMENTS = 200_000
MAX_FACTS = 100_000
MAX_CONCEPT_CANDIDATES = 100
XHTML = 'http://www.w3.org/1999/xhtml'
IXBRL = 'http://www.xbrl.org/2013/inlineXBRL'
XBRLI = 'http://www.xbrl.org/2003/instance'
ISO4217 = 'http://www.xbrl.org/2003/iso4217'
IFRS_NS = re.compile(r'^https?://xbrl\.ifrs\.org/taxonomy/[0-9]{4}-[0-9]{2}-[0-9]{2}/ifrs-full$')
TRANSFORMS = {
    'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12':
        {'num-dot-decimal': 'DOT', 'num-comma-decimal': 'COMMA'},
    'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26':
        {'numdotdecimal': 'DOT', 'numcommadecimal': 'COMMA'},
}
# Small issuer-independent set; extension elements are explicitly not inferred.
CONCEPTS = {
    'Revenue': 'REVENUE',
    'RevenueFromContractsWithCustomers': 'REVENUE',
    'ProfitLoss': 'PROFIT_LOSS',
    'ProfitLossAttributableToOwnersOfParent': 'PROFIT_PARENT',
}


def _qualified(qname: str, prefixes: dict) -> tuple[str, str]:
    if not isinstance(qname, str) or qname.count(':') != 1:
        return '', ''
    prefix, local = qname.split(':')
    return prefixes.get(prefix, ''), local


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _text_only(node) -> str:
    # Non-fraction facts sometimes contain nested formatting; intentionally
    # reject instead of concatenating text that could change the value.
    if len(node):
        raise ValueError('Nested iXBRL numeric markup needs specialist review')
    return (node.text or '').strip()


def _numeric(node, prefixes: dict) -> str:
    if node.get('nil') in ('true', '1') or any(_local(k) == 'nil' and v in ('true','1') for k,v in node.attrib.items()):
        raise ValueError('Nil iXBRL value')
    raw = _text_only(node)
    fmt = node.get('format')
    mode = None
    if fmt:
        ns, name = _qualified(fmt, prefixes)
        mode = TRANSFORMS.get(ns, {}).get(name)
        if not mode:
            raise ValueError('Unsupported iXBRL numeric transformation')
    if not raw or len(raw) > 100:
        raise ValueError('Missing or oversized iXBRL number')
    if mode == 'DOT':
        if not re.fullmatch(r'(?:\d{1,3}(?:[, ]\d{3})+|\d+)(?:\.\d+)?', raw):
            raise ValueError('Invalid dot-decimal transform')
        cleaned = raw.replace(',', '').replace(' ', '')
    elif mode == 'COMMA':
        if not re.fullmatch(r'(?:\d{1,3}(?:[. ]\d{3})+|\d+)(?:,\d+)?', raw):
            raise ValueError('Invalid comma-decimal transform')
        cleaned = raw.replace('.', '').replace(' ', '').replace(',', '.')
    else:
        if not re.fullmatch(r'\d+(?:\.\d+)?', raw):
            raise ValueError('Numeric fact needs a supported explicit transformation')
        cleaned = raw
    if node.get('sign', '') not in ('', '-', '+'):
        raise ValueError('Unsupported iXBRL sign')
    try:
        scale = int(node.get('scale', '0'))
        if not -9 <= scale <= 12:
            raise ValueError('Unsupported iXBRL scale')
        value = Decimal(cleaned) * (Decimal(10) ** scale)
        if node.get('sign') == '-': value = -value
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError('Invalid iXBRL numeric content') from exc
    if not value.is_finite() or abs(value) > Decimal('1e17'):
        raise ValueError('Out-of-range iXBRL numeric content')
    return str(value)


def _parse_tree(content: bytes):
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_XHTML_BYTES:
        raise ValueError('ESEF XHTML exceeds bounded parser size or is empty')
    prefixes = {}
    nodes = 0
    try:
        parser = SafeET.iterparse(io.BytesIO(content), events=('start-ns', 'start', 'end'))
        for event, elem in parser:
            if event == 'start-ns':
                prefix, uri = elem
                if prefix in prefixes and prefixes[prefix] != uri:
                    raise ValueError('ESEF namespace prefix rebound: unsupported')
                prefixes[prefix] = uri
            elif event == 'start':
                nodes += 1
                if nodes > MAX_XML_ELEMENTS:
                    raise ValueError('ESEF XHTML exceeds XML element budget')
        root = parser.root
    except (SafeET.ParseError, ValueError) as exc:
        if isinstance(exc, ValueError): raise
        raise ValueError('Unsafe or malformed ESEF XHTML') from exc
    if root.tag != f'{{{XHTML}}}html':
        raise ValueError('Expected a well-formed XHTML root')
    return root, prefixes


def _contexts(root, fiscal_year_end: date):
    contexts = {}
    identities = set()
    for node in root.iter(f'{{{XBRLI}}}context'):
        context_id = node.get('id')
        if not context_id or context_id in contexts:
            raise ValueError('Missing or duplicated XBRL context ID')
        identifier = node.find(f'./{{{XBRLI}}}entity/{{{XBRLI}}}identifier')
        if identifier is None or not (identifier.text or '').strip() or not identifier.get('scheme'):
            continue
        identities.add((identifier.get('scheme'),identifier.text.strip()))
        if node.find(f'.//{{{XBRLI}}}segment') is not None or node.find(f'.//{{{XBRLI}}}scenario') is not None:
            continue  # dimensioned segment data never used for issuer-wide metrics
        start = node.find(f'./{{{XBRLI}}}period/{{{XBRLI}}}startDate')
        end = node.find(f'./{{{XBRLI}}}period/{{{XBRLI}}}endDate')
        if start is None or end is None or not start.text or not end.text:
            continue  # instant facts not annual income-statement facts
        try:
            left, right = date.fromisoformat(start.text), date.fromisoformat(end.text)
        except ValueError: continue
        if not 300 <= (right-left).days <= 390 or right > fiscal_year_end:
            continue
        # Require current fiscal year end to avoid mixup with prior-period values.
        if right == fiscal_year_end:
            contexts[context_id] = {'start': str(left), 'end': str(right)}
    if len(identities) > 1:
        raise ValueError('Multiple XBRL reporting entities in a single filing')
    return contexts, next(iter(identities), None)


def _units(root, prefixes):
    allowed = set()
    for node in root.iter(f'{{{XBRLI}}}unit'):
        unit_id = node.get('id')
        if not unit_id: continue
        measures = list(node.iter(f'{{{XBRLI}}}measure'))
        # Reject ratios and complex units.
        if len(measures) != 1 or len(node) != 1 or _local(node[0].tag) != 'measure':
            continue
        namespace, currency = _qualified((measures[0].text or '').strip(), prefixes)
        if namespace == ISO4217 and currency == 'EUR':
            allowed.add(unit_id)
    return allowed


def extract_ixbrl_ifrs_candidates(content: bytes, fiscal_year_end: date) -> dict:
    """Extract *candidate* IFRS EUR figures, never certify issuer financials.

    Supports a narrow, explicit subset of Inline XBRL 1.1 and transformation
    registry formats. A present but unsupported transform is reported, not guessed.
    """
    root, prefixes = _parse_tree(content)
    contexts, identity = _contexts(root, fiscal_year_end)
    units = _units(root, prefixes)
    selected = []
    rejected = defaultdict(int)
    nonfractions = root.iter(f'{{{IXBRL}}}nonFraction')
    total = 0
    for node in nonfractions:
        total += 1
        if total > MAX_FACTS:
            raise ValueError('ESEF XHTML exceeds iXBRL fact budget')
        namespace, concept = _qualified(node.get('name'), prefixes)
        if not IFRS_NS.fullmatch(namespace) or concept not in CONCEPTS:
            continue
        context = contexts.get(node.get('contextRef'))
        if context is None:
            rejected['NO_CURRENT_UNDIMENSIONED_ANNUAL_CONTEXT'] += 1
            continue
        if node.get('unitRef') not in units:
            rejected['UNSUPPORTED_OR_NON_EUR_UNIT'] += 1
            continue
        if node.get('continuedAt') or node.get('tupleRef'):
            rejected['CONTINUATION_OR_TUPLE_UNSUPPORTED'] += 1
            continue
        try:
            value = _numeric(node, prefixes)
        except ValueError:
            rejected['NUMERIC_TRANSFORMATION_REQUIRES_REVIEW'] += 1
            continue
        selected.append({'metric':CONCEPTS[concept], 'concept':concept, 'value_eur':value,
                         'context_id':node.get('contextRef'), 'unit_id':node.get('unitRef'),
                         'period_start':context['start'], 'period_end':context['end'],
                         'transformation':node.get('format', 'UNFORMATTED'),
                         'decimals':node.get('decimals', 'UNSPECIFIED')})
        if len(selected) > MAX_CONCEPT_CANDIDATES:
            raise ValueError('Too many candidate IFRS facts; specialist review required')
    # Duplicate facts may be repeated in an XHTML report; preserve duplicate values
    # and flag conflicts rather than silently choosing one.
    grouped = defaultdict(set)
    for fact in selected:
        grouped[(fact['metric'],fact['concept'])].add(fact['value_eur'])
    conflicts = sorted(f'{metric}:{concept}' for (metric,concept),values in grouped.items() if len(values)>1)
    selected.sort(key=lambda f:(f['metric'],f['concept'],f['context_id'],f['value_eur']))
    return {'status':('IFRS_CANDIDATES_REQUIRE_HUMAN_TAXONOMY_AND_AUDIT_REVIEW' if selected
                       else 'NO_SUPPORTED_UNDIMENSIONED_EUR_IFRS_CANDIDATES'),
            'reporting_entity_identifier':(identity[1] if identity else None),
            'reporting_entity_scheme':(identity[0] if identity else None),
            'candidate_count':len(selected), 'conflicting_concepts':conflicts,
            'rejected_fact_reasons':dict(sorted(rejected.items())),
            'facts':selected, 'verified_fundamental_count':0,
            'limitations':['Only explicitly supported IFRS standard concepts, EUR units and current-year dimensionless duration contexts.',
                           'Source URL, publication date, LEI, taxonomy extension/anchoring, audit and consolidation are not authenticated.',
                           'Values require comparison against issuer published statements; no market score or trading decision.']}
