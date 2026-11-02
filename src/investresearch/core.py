"""Pure functions: costs, scenario maths, conservative fiscal triage.

No broker integration. Financial and fiscal calculations are research estimates,
not verified tax statements; the exact broker fiscal base can differ.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Mapping

D = lambda x: Decimal(str(x))

def cents(x: Decimal) -> Decimal:
    return x.quantize(D('0.01'), rounding=ROUND_HALF_UP)

@dataclass(frozen=True)
class Fees:
    rate: Decimal = D('0.002')
    minimum: Decimal = D('5')
    maximum: Decimal = D('25')
    italy_share_ftt_rate: Decimal = D('0.002')

    def order(self, consideration: Decimal) -> Decimal:
        consideration = D(consideration)
        if not consideration.is_finite() or consideration <= 0:
            raise ValueError('Order notional must be positive')
        return cents(max(self.minimum, min(self.maximum, consideration*self.rate)))

@dataclass(frozen=True)
class TradeScenario:
    invested_eur: Decimal
    hypothetical_return: Decimal
    buy_cost_eur: Decimal
    sell_cost_eur: Decimal
    ftt_eur: Decimal
    fx_conversion_cost_eur: Decimal
    gross_pnl_eur: Decimal
    net_pnl_before_unverified_costs_eur: Decimal
    buy_notional_eur: Decimal
    sell_notional_eur: Decimal

def evaluate_position(invested_eur, hypothetical_return, fees: Fees, italy_ftt: bool=False, fx_spread_bps: Decimal=D(0)) -> TradeScenario:
    n, r = D(invested_eur), D(hypothetical_return)
    if not n.is_finite() or not r.is_finite() or n <= 0 or r < -1:
        raise ValueError('Invalid capital or return')
    sale = n*(1+r)
    buyfee = fees.order(n)
    sellfee = fees.order(sale) if sale > 0 else D('0')
    ftt = cents(n*fees.italy_share_ftt_rate) if italy_ftt else D('0')
    fx = cents((n+sale)*D(fx_spread_bps)/D('10000'))
    gross = cents(sale-n)
    return TradeScenario(n,r,buyfee,sellfee,ftt,fx,gross,cents(gross-buyfee-sellfee-ftt-fx),n,sale)

def apply_loss_carryforward(eligible_realized_gain, losses, tax_rate=D('0.26')):
    """Illustrative tax saving for net eligible gains, BEFORE broker verification.
    Input should already reflect any contemporaneous offsetting realized losses.
    """
    if not D(eligible_realized_gain).is_finite() or not D(losses).is_finite():
        raise ValueError('Non-finite tax inputs')
    taxable = max(D('0'), D(eligible_realized_gain))
    offset = min(taxable, max(D('0'), D(losses)))
    return {'potential_offset_eur':cents(offset), 'potential_tax_avoided_eur':cents(offset*D(tax_rate))}

def settle_weekdays(trade_day:date, lag:int, holidays=()):
    """Simplified business-day settlement; lacks national/venue/custom holidays.
    This MUST NOT be used as a verified tax-recognition calendar.
    """
    holidays=set(holidays)
    day=trade_day
    for _ in range(lag):
        day += timedelta(days=1)
        while day.weekday()>=5 or day in holidays:
            day += timedelta(days=1)
    return day

def validate_allocation(positions: Mapping[str,int], cash_eur:int, capital:int, max_positions:int):
    if any(x <= 0 for x in positions.values()) or cash_eur < 0:
        raise ValueError('Negative or zero positions / negative cash')
    if len(positions)>max_positions:
        raise ValueError('Too many positions')
    if sum(positions.values()) + cash_eur != capital:
        raise ValueError('Portfolio does not reconcile to capital')
