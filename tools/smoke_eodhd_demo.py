"""One bounded three-endpoint EODHD evaluation demo test on ephemeral CI.

Do not print or persist raw vendor prices, splits, dividends, licence keys or
computed financial values. A demo does NOT authenticate source rights or make
a price bundle eligible for screening.
"""
from datetime import date

from investresearch.research_eodhd_pilot import run_demo


def main():
    try:
        result = run_demo(as_of=date(2026, 11, 5), live_confirm=True)
    except ValueError as exc:
        if str(exc) == "Provider unreachable or DEMO entitlement unavailable":
            print("EODHD_DEMO_CLASSIFICATION=SOURCE_UNAVAILABLE_NOT_VALIDATED")
            return 0
        print("EODHD_DEMO_CLASSIFICATION=PAYLOAD_VALIDATION_FAILED")
        return 2
    if (result["available_eod_sessions"] < 61
            or not result["last_61_contiguous_nasdaq_sessions"]
            or result["license_validated_for_private_production"]
            or not result["demo_data_not_trade_ready"]
            or result["market_price_score"] is not None):
        print("EODHD_DEMO_CLASSIFICATION=INTEGRITY_INVARIANTS_FAILED")
        return 2
    print("EODHD_DEMO_CLASSIFICATION=EOD_SPLITS_DIVIDENDS_VALIDATED_DEMO_ONLY")
    print("EODHD_DEMO_61_SESSIONS=PASS")
    print("EODHD_DEMO_RIGHTS_AND_TRADE_READINESS=UNVERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
