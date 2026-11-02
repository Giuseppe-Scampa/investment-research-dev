"""Date-aware illustrative netting of financial *redditi diversi*.

The calculations never certify the fiscal recognition date, broker processing,
product tax treatment, or an actual wallet balance. Existing losses are consumed
only against same-day or later gains.  Same-day income is netted by tax category;
capital income never consumes the offset wallet.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from .core import D, cents
from .tax_engine import DIFFERENT, CAPITAL, wallet_offset


def net_realizations(realizations, wallets, account_id, year, regime='amministrato'):
    """Return a tax-impact simulation with dated, category-separated entries.

    Each event requires date, event (gain/loss/neutral), category, signed
    compensable_eur (or compensable magnitude for loss) and tax_rate.
    The full raw tax result is retained in individual position results.
    """
    dates = defaultdict(list)
    for rec in realizations:
        day = date.fromisoformat(rec['realization_date'])
        if day.year != year:
            raise ValueError('Realization is outside the simulated fiscal year')
        dates[day].append(rec)

    balances = [dict(w) for w in wallets]
    consumed_by_vintage = defaultdict(lambda: D(0))
    total_current_losses_applied = D(0)
    cumulative_current_losses = D(0)
    remaining_new_losses = D(0)
    eligible_after_current_losses = D(0)
    wallet_applied = D(0)
    unpaid_diverse = D(0)
    capital_tax = D(0)
    capital_gains = D(0)
    total_gross_different_gains = D(0)
    total_gross_different_losses = D(0)
    unresolved = []
    timeline = []

    for day in sorted(dates):
        date_gains = date_losses = D(0)
        date_capital_tax = D(0)
        for event in dates[day]:
            category = event['category']
            kind = event['fiscal_event']
            amount = D(event['compensable_eur'])
            if not amount.is_finite() or amount < 0:
                raise ValueError('Non-finite or negative compensable magnitude')
            if category == DIFFERENT:
                if kind == 'gain':
                    date_gains += amount
                elif kind == 'loss':
                    date_losses += amount
            elif category == CAPITAL and kind == 'gain':
                net = D(event['hypothetical_realized_net_eur'])
                rate = D(event['tax_rate'])
                if not (net.is_finite() and net >= 0 and rate.is_finite() and 0 <= rate <= 1):
                    raise ValueError('Invalid taxable income or tax rate')
                capital_gains += net
                date_capital_tax += cents(net * rate)
            elif category not in (DIFFERENT, CAPITAL, 'NOT_APPLICABLE'):
                unresolved.append(event.get('position_id','?'))
        total_gross_different_gains += date_gains
        total_gross_different_losses += date_losses
        cumulative_current_losses += date_losses
        applied_current = min(cumulative_current_losses, date_gains)
        cumulative_current_losses -= applied_current
        total_current_losses_applied += applied_current
        gain_after_current = date_gains - applied_current
        eligible_after_current_losses += gain_after_current

        # Existing eligible carryforwards can be applied to positive, dated gains
        # only after same-day/prior current-year losses are used.
        offset = wallet_offset(balances, gain_after_current, account_id, year, regime=regime)
        used = D(offset['compensated_eur'])
        wallet_applied += used
        for allocation in offset['allocations']:
            vintage = int(allocation['vintage'])
            quantity = D(allocation['used_eur'])
            consumed_by_vintage[vintage] += quantity
            for w in balances:
                if w['account_id'] == account_id and w['tax_regime'] == regime and int(w['year']) == vintage:
                    old = D(w['remaining_eur'])
                    w['remaining_eur'] = str(cents(old - quantity))
                    break
        unpaid = D(offset['uncompensated_eur'])
        unpaid_diverse += unpaid
        capital_tax += date_capital_tax
        timeline.append({'date':day.isoformat(), 'different_gains_eur':str(cents(date_gains)),
                         'different_losses_eur':str(cents(date_losses)),
                         'same_year_losses_applied_eur':str(cents(applied_current)),
                         'prior_wallet_applied_eur':str(cents(used)),
                         'uncompensated_different_eur':str(cents(unpaid)),
                         'capital_income_tax_eur':str(cents(date_capital_tax))})

    rate = D('.26')
    tax_other = cents(unpaid_diverse * rate)
    tax_avoided = cents(wallet_applied * rate)
    return {
        'different_gross_gains_eur':str(cents(total_gross_different_gains)),
        'different_gross_losses_eur':str(cents(total_gross_different_losses)),
        'same_year_losses_applied_eur':str(cents(total_current_losses_applied)),
        'eligible_net_gain_eur':str(cents(eligible_after_current_losses)),
        'unused_current_year_loss_eur':str(cents(cumulative_current_losses)),
        'capital_income_gains_eur':str(cents(capital_gains)),
        'wallet':{'compensated_eur':str(cents(wallet_applied)),
                  'uncompensated_eur':str(cents(unpaid_diverse)),
                  'potential_tax_avoided_eur':str(tax_avoided),
                  'allocations':[{'vintage':v,'used_eur':str(cents(a))}
                                 for v,a in sorted(consumed_by_vintage.items())],
                  'verification':'ESTIMATED_NOT_BROKER_CONFIRMED'},
        'estimated_income_tax_eur':str(cents(capital_tax + tax_other)),
        'estimated_capital_income_tax_eur':str(cents(capital_tax)),
        'estimated_unoffset_different_tax_eur':str(tax_other),
        'unresolved_tax_positions':sorted(set(unresolved)),
        'timeline':timeline,
        'fiscal_status':'INCOMPLETE' if unresolved else 'ESTIMATED_NOT_CERTIFIED',
        'note':'Order follows supplied illustrative realization dates; no broker fiscal date assumed.',
    }
