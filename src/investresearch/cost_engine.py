"""Gross cash economics; no unknown execution spread silently set to verified zero."""
from __future__ import annotations
from decimal import Decimal, ROUND_CEILING
from .core import D, cents, Fees


def trade_costs(quantity, price_eur, fees: Fees, *, side='buy',
                italy_ftt_status='unknown', fx_bps=None, spread_bps=None):
    q, p = D(quantity), D(price_eur)
    if not q.is_finite() or q <= 0 or not p.is_finite() or p <= 0:
        raise ValueError('Invalid quantity or price')
    if side not in ('buy', 'sell'):
        raise ValueError('Unknown side')
    n = q * p
    broker = fees.order(n)
    ftt = cents(n * fees.italy_share_ftt_rate) if side == 'buy' and italy_ftt_status == 'yes' else D('0')
    if italy_ftt_status not in ('yes', 'no', 'unknown'):
        raise ValueError('Unknown FTT scope')
    for label, bps in [('FX', fx_bps), ('spread', spread_bps)]:
        if bps is not None and (not D(bps).is_finite() or D(bps) < 0 or D(bps) >= 10000):
            raise ValueError(f'Invalid {label} cost in basis points')
    fx = cents(n * D(fx_bps) / D(10000)) if fx_bps is not None else D(0)
    spread = cents(n * D(spread_bps) / D(10000)) if spread_bps is not None else D(0)
    allcosts = broker + ftt + fx + spread
    return {'notional_eur': str(cents(n)), 'commission_eur': str(broker),
            'ftt_eur': str(ftt), 'fx_eur': str(fx), 'spread_eur': str(spread),
            'outlay_eur': str(cents(n + allcosts)) if side == 'buy' else None,
            'net_proceeds_eur': str(cents(n - allcosts)) if side == 'sell' else None,
            'total_explicit_cost_eur': str(cents(allcosts)),
            'status': 'INCOMPLETE' if italy_ftt_status == 'unknown' or spread_bps is None or fx_bps is None else 'ESTIMATED',
            'scope_note': 'Unknown FTT/spread/FX means estimate is a lower-bound, not final execution cost'}


def affordable_units(cash_eur, unit_price_eur, fees: Fees, **kwargs):
    cash, price = D(cash_eur), D(unit_price_eur)
    if not cash.is_finite() or cash < 0 or not price.is_finite() or price <= 0:
        raise ValueError('Invalid cash/unit price')
    high, low = int(cash / price), 0
    while low < high:
        mid = (low + high + 1) // 2
        quote = trade_costs(mid, price, fees, side='buy', **kwargs)
        if D(quote['outlay_eur']) <= cash:
            low = mid
        else:
            high = mid - 1
    return low


def break_even_sell_unit_price(qty, buy_unit_price, fees: Fees, **kwargs):
    """Find the smallest cent-unit sell price covering all known roundtrip costs.

    The upper limit expands adaptively; a 10x bound misses micro-holdings
    where minimum broker commissions dominate. Market quote ticks may differ.
    """
    buy = trade_costs(qty, buy_unit_price, fees, side='buy', **kwargs)
    needed = D(buy['outlay_eur'])
    hi = max(D('.01'), D(buy_unit_price))
    for _ in range(256):
        if D(trade_costs(qty, hi, fees, side='sell', **kwargs)['net_proceeds_eur']) >= needed:
            break
        hi *= 2
    else:
        raise ValueError('Unable to find a break-even price within supported limits')
    lo = D('0')
    for _ in range(90):
        mid = (hi + lo) / 2
        if D(trade_costs(qty, mid, fees, side='sell', **kwargs)['net_proceeds_eur']) >= needed:
            hi = mid
        else:
            lo = mid
    result = hi.quantize(D('.01'), rounding=ROUND_CEILING)
    if result <= 0:
        result = D('.01')
    # Rounded trading fees can move the exact boundary by one cent.
    for _ in range(12):
        sale = trade_costs(qty, result, fees, side='sell', **kwargs)
        if D(sale['net_proceeds_eur']) >= needed:
            return result
        result += D('.01')
    raise ValueError('Could not reconcile cent-rounded break-even price')
