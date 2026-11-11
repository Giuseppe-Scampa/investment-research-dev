"""The retrospective pilot must never silently rerun on a changed daily CSV."""
from pathlib import Path
import importlib.util

import pytest


def test_daily_source_sha_change_is_explicitly_blocked_without_outcomes(monkeypatch, capsys):
    path = Path(__file__).resolve().parents[1] / "tools" / "pilot_real_sp500_backtest_v2.py"
    spec = importlib.util.spec_from_file_location("v2_secondary_pilot_status_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_fetch", lambda url, limit: b"FICTITIOUS_CHANGED_VENDOR_DAILY_CSV")
    with pytest.raises(SystemExit) as raised:
        mod.main()
    assert raised.value.code == 3
    assert capsys.readouterr().out.strip() == (
        "PREREGISTERED_ORIGINAL_MARKET_DATA_SHA_CHANGED; NO_RETROSPECTIVE_RESULTS")
