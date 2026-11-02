"""Existing positions: documented tax-basis modes only; no implicit FIFO/LIFO."""
from __future__ import annotations
from decimal import Decimal
from datetime import date
from .core import D, cents


def sale_cost_basis(position, units):
    units = D(units)
    if not units.is_finite() or units <= 0:
        raise ValueError('Invalid sale quantity')
    lots = position.get('lots', [])
    for lot in lots:
        if lot.get('purchase_date'):
            try:
                date.fromisoformat(lot['purchase_date'])
            except ValueError as exc:
                raise ValueError('Invalid purchase date') from exc
    held = sum((D(lot['quantity']) for lot in lots), D(0))
    if any(not D(lot['quantity']).is_finite() or D(lot['quantity']) < 0 for lot in lots):
        raise ValueError('Invalid lot quantity')
    if units > held:
        raise ValueError('Sold quantity exceeds documented holdings')
    method = position.get('tax_cost_method')
    if method == 'BROKER_REPORTED_AVERAGE':
        average = D(position['broker_tax_unit_cost_eur'])
        if not average.is_finite() or average < 0:
            raise ValueError('Invalid broker average tax basis')
        return cents(units * average), 'BROKER_REPORTED_AVERAGE'
    if method != 'EXPLICIT_LOT_SELECTION':
        raise ValueError('Tax cost basis unspecified; do not assume FIFO or average')
    allocation = position.get('sale_lot_allocations', [])
    ids = [l['lot_id'] for l in lots]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate lot IDs')
    if len({a['lot_id'] for a in allocation}) != len(allocation):
        raise ValueError('Duplicate sale lot allocations')
    by_id = {l['lot_id']: l for l in lots}
    total, basis = D(0), D(0)
    for alloc in allocation:
        if alloc['lot_id'] not in by_id:
            raise ValueError('Unknown lot')
        qty = D(alloc['quantity'])
        lot = by_id[alloc['lot_id']]
        if not qty.is_finite() or qty <= 0 or qty > D(lot['quantity']):
            raise ValueError('Invalid allocation')
        unit = D(lot['tax_unit_cost_eur'])
        if not unit.is_finite() or unit < 0:
            raise ValueError('Invalid fiscal lot cost')
        total += qty
        basis += qty * unit
    if total != units:
        raise ValueError('Sale allocation does not reconcile to quantity')
    return cents(basis), 'ILLUSTRATIVE_SELECTED_LOTS_NOT_BROKER_METHOD'


def local_to_eur(price, fx_eur_per_unit):
    price, fx = D(price), D(fx_eur_per_unit)
    if not all(v.is_finite() and v > 0 for v in (price, fx)):
        raise ValueError('Missing/invalid explicitly supplied FX rate')
    return cents(price * fx)
