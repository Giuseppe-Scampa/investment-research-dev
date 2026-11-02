"""Conservative, versioned Italian fiscal *research* simulator.

Categories for EACH event are distinct. No automatic broker certificate or
personal tax account verification. Unsupported classes must not be assumed eligible.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from .core import D, cents

DIFFERENT = 'REDDITI_DIVERSI'
CAPITAL = 'REDDITI_CAPITALE'
UNKNOWN = 'REVIEW_REQUIRED'
VALID_CATEGORIES = {DIFFERENT, CAPITAL, UNKNOWN}

@dataclass(frozen=True)
class FiscalRule:
    rule_id: str
    asset_type: str
    valid_from: date
    valid_to: date
    gain_category: str
    loss_category: str
    periodic_category: str
    taxable_factor: Decimal
    tax_rate: Decimal
    verification: str
    source_url: str
    isin: str = ''

    def category(self, event):
        return {'gain': self.gain_category, 'loss': self.loss_category,
                'periodic': self.periodic_category}[event]


class FiscalRegistry:
    def __init__(self, records):
        self.rules = []
        for r in records:
            if any(r[key] not in VALID_CATEGORIES for key in ('gain_category', 'loss_category', 'periodic_category')):
                raise ValueError('Invalid fiscal category')
            valid_from, valid_to = date.fromisoformat(r['valid_from']), date.fromisoformat(r['valid_to'])
            if valid_from > valid_to:
                raise ValueError('Inverted fiscal date interval')
            factor, rate = D(r['taxable_factor']), D(r['tax_rate'])
            if not (factor.is_finite() and 0 <= factor <= 1 and rate.is_finite() and 0 <= rate <= 1):
                raise ValueError('Invalid fiscal factor/rate')
            if not r.get('source_url', '').startswith('https://'):
                raise ValueError('Fiscal rule without public provenance')
            self.rules.append(FiscalRule(r['rule_id'], r['asset_type'], valid_from,
                valid_to, r['gain_category'], r['loss_category'], r['periodic_category'],
                factor, rate, r['verification'], r['source_url'], r.get('isin', '')))
        keys = [(r.rule_id, r.valid_from) for r in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate fiscal rule')

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8'))['rules'])

    def get(self, asset_type, event_date: date, isin=''):
        matches = [r for r in self.rules if r.asset_type == asset_type
                   and r.valid_from <= event_date <= r.valid_to
                   and (not r.isin or r.isin == isin)]
        exact = [r for r in matches if r.isin and r.isin == isin]
        viable = exact if exact else [r for r in matches if not r.isin]
        if len(viable) != 1:
            raise ValueError(f'Missing/ambiguous fiscal rule for {asset_type} on {event_date}')
        return viable[0]


def classify_realization(proceeds_eur, tax_basis_eur, rule: FiscalRule):
    """Proceeds and tax basis must already be EUR and include only eligible costs.

    Returns the category, signed net delta and positive compensable amount.
    Does not net across accounts, incomes, or periods automatically.
    """
    proceeds, basis = D(proceeds_eur), D(tax_basis_eur)
    if not all(v.is_finite() and v >= 0 for v in (proceeds, basis)):
        raise ValueError('Invalid EUR realization amounts')
    net = cents(proceeds - basis)
    event = 'gain' if net > 0 else 'loss' if net < 0 else 'neutral'
    category = rule.category(event) if event != 'neutral' else 'NOT_APPLICABLE'
    compensated = (cents(abs(net) * rule.taxable_factor) if category == DIFFERENT else D('0.00'))
    return {'event': event, 'category': category, 'net_eur': str(net),
            'compensable_eur': str(compensated),
            'fiscal_status': 'DOCUMENTED_GENERIC' if rule.verification == 'DOCUMENTED_GENERIC'
                             else 'REVIEW_REQUIRED',
            'taxable_factor': str(rule.taxable_factor), 'tax_rate': str(rule.tax_rate),
            'source': rule.source_url, 'rule_id': rule.rule_id}


def wallet_offset(wallets, gain_eur, account_id, year, *, regime='amministrato', rate=D('.26')):
    """Illustrative offsets oldest first *within same verified account/regime*.

    Unverified personal balance makes the outcome ESTIMATED; not an executed tax event.
    """
    left = D(gain_eur)
    if not left.is_finite() or left < 0:
        raise ValueError('Gain must be a finite positive amount')
    entries = [dict(w) for w in wallets if w['account_id'] == account_id
               and w['tax_regime'] == regime and int(w['year']) <= year
               and year <= int(w['year']) + 4]
    entries.sort(key=lambda x: int(x['year']))
    used = []
    for w in entries:
        available = D(w['remaining_eur'])
        if not available.is_finite() or available < 0:
            raise ValueError('Invalid wallet balance')
        consumed = min(available, left)
        left -= consumed
        used.append({'vintage': int(w['year']), 'used_eur': str(cents(consumed)),
                     'status': w.get('verification_status', 'UNVERIFIED')})
    total = D(gain_eur) - left
    return {'compensated_eur': str(cents(total)), 'uncompensated_eur': str(cents(left)),
            'potential_tax_avoided_eur': str(cents(total * D(rate))),
            'allocations': used,
            'verification': 'DOCUMENTED' if entries and all(x.get('verification_status') == 'DOCUMENTED' for x in entries)
                            else 'ESTIMATED_NOT_BROKER_CONFIRMED'}


def expired_potential(wallets, year, rate=D('.26')):
    result = []
    for w in wallets:
        if int(w['year']) + 4 == year:
            amount = D(w['remaining_eur'])
            result.append({'account_id': w['account_id'], 'vintage': w['year'],
                           'expires': f'{year}-12-31', 'balance_eur': str(amount),
                           'maximum_theoretical_tax_value_eur': str(cents(amount * D(rate))),
                           'status': w.get('verification_status', 'UNVERIFIED')})
    return result
