"""Fail-closed XBRL unit identity checks, using only synthetic XHTML."""
from datetime import date

import pytest

from investresearch.research_ixbrl import extract_ixbrl_ifrs_candidates


PREFIX = """<html xmlns="http://www.w3.org/1999/xhtml"
xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
xmlns:xbrli="http://www.xbrl.org/2003/instance"
xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
xmlns:ifrs-full="https://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full">
<body><ix:header><ix:resources>
<xbrli:context id="FY">
<xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">
12345678901234567890</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate>
<xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
</xbrli:context>
"""
FACT = """<ix:nonFraction name="ifrs-full:Revenue" contextRef="FY"
unitRef="U" scale="6">123</ix:nonFraction>"""


def unit(unit_id, currency="EUR"):
    attr = f' id="{unit_id}"' if unit_id is not None else ""
    return (f"<xbrli:unit{attr}><xbrli:measure>iso4217:{currency}</xbrli:measure>"
            "</xbrli:unit>")


def ratio(unit_id):
    return (f'<xbrli:unit id="{unit_id}"><xbrli:divide>'
            '<xbrli:unitNumerator><xbrli:measure>iso4217:EUR</xbrli:measure>'
            '</xbrli:unitNumerator><xbrli:unitDenominator>'
            '<xbrli:measure>iso4217:USD</xbrli:measure>'
            '</xbrli:unitDenominator></xbrli:divide></xbrli:unit>')


def extract(units):
    payload = (PREFIX + units + "</ix:resources></ix:header>" + FACT
               + "</body></html>").encode("utf-8")
    return extract_ixbrl_ifrs_candidates(payload, date(2025, 12, 31))


@pytest.mark.parametrize("colliding_unit", [
    unit("U", "EUR"),  # Even an identical definition violates ID uniqueness.
    unit("U", "USD"),  # Different currency cannot borrow the EUR declaration.
    ratio("U"),        # Previously unsupported ratios could shadow an EUR ID.
])
def test_duplicate_unit_id_is_rejected_even_if_second_is_unsupported(colliding_unit):
    with pytest.raises(ValueError, match="duplicated XBRL unit ID"):
        extract(unit("U") + colliding_unit)


def test_invalid_unit_before_valid_declaration_cannot_share_id():
    with pytest.raises(ValueError, match="duplicated XBRL unit ID"):
        extract(unit("U", "USD") + unit("U", "EUR"))


def test_missing_unit_id_refused_even_on_irrelevant_unit():
    with pytest.raises(ValueError, match="Missing or duplicated XBRL unit ID"):
        extract(unit("U", "EUR") + unit(None, "USD"))


def test_valid_distinct_units_keep_eur_fact_unmodified():
    result = extract(unit("U", "EUR") + unit("USD", "USD") + ratio("RATIO"))
    assert result["candidate_count"] == 1
    assert result["facts"][0]["value_eur"] == "123000000"
    assert result["verified_fundamental_count"] == 0


def test_no_matching_eur_unit_stays_unranked():
    result = extract(unit("U", "USD"))
    assert result["candidate_count"] == 0
    assert result["rejected_fact_reasons"] == {"UNSUPPORTED_OR_NON_EUR_UNIT": 1}
