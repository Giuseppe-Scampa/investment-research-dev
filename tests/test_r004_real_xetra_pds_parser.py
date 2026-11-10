"""No raw market data in repository: validate PDS schema with fictional rows."""
import pytest
from tools.probe_public_xetra_pds_historical import strict_probe


def payload():
    return ("ISIN,Date,Time,StartPrice,MaxPrice,MinPrice,EndPrice,TradedVolume,Currency\\n"
            "DE0005810055,2019-04-18,14:00:00,100.0,101.0,99.0,100.5,200,EUR\\n"
            "DE000BASF111,2019-04-18,14:01:00,60.0,60.0,59.0,59.8,100,EUR\\n").encode()


def test_public_source_parser_never_exports_raw_prices():
    report=strict_probe(payload(),"2019-04-18")
    assert report["minute_observation_count"]==2
    assert report["distinct_isin_count"]==2
    assert report["real_source_retrieved"] is True  # test function validates payload only
    assert report["is_adjusted_daily_close"] is False
    assert report["backtest_ready"] is False
    assert "100.5" not in str(report)


def test_public_source_parser_rejects_wrong_date_and_price_inversions():
    with pytest.raises(ValueError,match="date"):
        strict_probe(payload(),"2019-04-19")
    with pytest.raises(ValueError,match="inconsistent"):
        strict_probe(payload().replace(b"101.0",b"90.0"),"2019-04-18")
