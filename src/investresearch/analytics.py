"""Numerical indicators on validated *adjusted* closes; never executable quotes."""
from math import isfinite, sqrt
from statistics import mean, stdev


def _validated(prices):
    prices = [float(v) for v in prices]
    if not all(isfinite(v) and v > 0 for v in prices):
        raise ValueError('Prices must be positive finite numbers')
    return prices


def returns(prices):
    p = _validated(prices)
    return [p[i] / p[i-1] - 1 for i in range(1, len(p))]


def wilder_rsi(prices, period=14):
    p = _validated(prices)
    if len(p) < period + 1:
        return None
    changes = [p[i] - p[i-1] for i in range(1, len(p))]
    avg_gain = sum(max(0, x) for x in changes[:period]) / period
    avg_loss = sum(max(0, -x) for x in changes[:period]) / period
    for change in changes[period:]:
        avg_gain = (avg_gain * (period-1) + max(0, change)) / period
        avg_loss = (avg_loss * (period-1) + max(0, -change)) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def indicators(closes):
    closes = _validated(closes)
    rr = returns(closes)
    out = {'observations': len(closes), 'last_close_adjusted': closes[-1] if closes else None}
    for p in (5, 20, 60, 120):
        out[f'return_{p}d'] = round(closes[-1]/closes[-p-1]-1, 6) if len(closes) > p else None
    for p in (20, 50, 200):
        out[f'ma_{p}'] = round(mean(closes[-p:]), 5) if len(closes) >= p else None
    out['annualized_vol_20d'] = round(stdev(rr[-20:]) * sqrt(252), 5) if len(rr) >= 20 else None
    rsi = wilder_rsi(closes)
    out['rsi_14'] = round(rsi, 4) if rsi is not None else None
    if len(closes) >= 20:
        peak, dd = closes[0], 0
        for v in closes:
            peak = max(peak, v)
            dd = min(dd, v / peak - 1)
        out['max_drawdown_available_history'] = round(dd, 6)
    else:
        out['max_drawdown_available_history'] = None
    out['data_quality'] = 'UNVALIDATED_ADJUSTED_HISTORY'
    return out


def pearson_aligned(a, b):
    if len(a) != len(b) or len(a) < 20:
        return None
    if not all(isfinite(float(v)) for v in list(a) + list(b)):
        raise ValueError('Returns must be finite')
    ma, mb = mean(a), mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return round(cov/(va*vb)**0.5, 5) if va > 0 and vb > 0 else None


def eur_adjusted_returns(price_by_date, fx_eur_per_local_by_date):
    """Strict inner-join by identical sessions. No missing FX interpolation."""
    if set(price_by_date) != set(fx_eur_per_local_by_date):
        raise ValueError('Missing/non-synchronous FX sessions; EUR returns unavailable')
    dates = sorted(price_by_date)
    return returns([float(price_by_date[d]) * float(fx_eur_per_local_by_date[d]) for d in dates])
