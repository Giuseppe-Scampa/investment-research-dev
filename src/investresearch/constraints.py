"""Hard portfolio exclusions vs advisory overlap and preference warnings."""
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Constraint:
    level: str
    code: str
    message: str


def instrument_constraints(instrument: dict, settings: dict, *, new_purchase=True):
    out = []
    sector = (instrument.get('sector') or '').lower()
    name = (instrument.get('name') or '').lower()
    if new_purchase and settings.get('exclude_additional_gold') and (sector in ('gold', 'precious metal gold') or re.search(r'\bgold\b', name)):
        out.append(Constraint('BLOCKED', 'gold', 'No additional gold'))
    if new_purchase and settings.get('exclude_primary_oil') and instrument.get('oil_exposure') in ('direct', 'predominant'):
        out.append(Constraint('BLOCKED', 'oil', 'Direct/predominant oil excluded'))
    if settings.get('avoid_duplicate_eurostoxx50'):
        memberships = instrument.get('index_memberships', [])
        if isinstance(memberships, str):
            memberships = [s.strip() for s in memberships.split(';') if s.strip()]
        if 'EURO_STOXX_50' in memberships:
            out.append(Constraint('REVIEW','overlap','Euro Stoxx 50 exposure: review concentration'))
        elif not memberships and instrument.get('index_membership_status') in ('UNKNOWN','UNVERIFIED'):
            out.append(Constraint('REVIEW','overlap_unverified','Euro Stoxx 50 membership not verified'))
    return out


def portfolio_constraints(positions: dict, cash_eur, settings: dict):
    out = []
    max_positions = int(settings.get('max_positions', 3))
    if len(positions) > max_positions:
        out.append(Constraint('BLOCKED', 'max_positions', 'Too many positions'))
    if len(positions) > int(settings.get('preferred_positions', 2)):
        out.append(Constraint('REVIEW', 'preferred_positions', 'More than preferred positions'))
    if float(cash_eur) < 0:
        out.append(Constraint('BLOCKED', 'negative_cash', 'Negative cash'))
    return out
