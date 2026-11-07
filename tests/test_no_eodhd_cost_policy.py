"""No-EODHD decision: normal CLI must never request EODHD or require its keys.

Legacy provider parser tests may remain for archival backwards compatibility;
the integrated user workflow has NO EODHD registration, billing or network.
"""
from __future__ import annotations

import json

import pytest

from investresearch.research_cli import main


@pytest.mark.parametrize("argv", [
    ["eodhd-personal-collect", "--symbol","TEST.XETRA",
     "--isin","US0378331005","--venue","XETR","--currency","EUR",
     "--name","Synthetic","--asset-type","EQUITY","--sector","Synthetic",
     "--oil-exposure","none","--acknowledge-personal-terms",
     "--identity-reviewed", "--output","/tmp/SHOULD_NOT_EXIST_EODHD"],
    ["eodhd-xetra-catalog-collect","--acknowledge-personal-terms",
     "--output","/tmp/SHOULD_NOT_EXIST_EODHD"],
    ["xetra-eodhd-crosswalk", "--xetra-raw","missing",
     "--xetra-meta","missing","--eodhd-raw","missing",
     "--eodhd-meta","missing","--as-of","2026-11-05",
     "--output","/tmp/SHOULD_NOT_EXIST_EODHD"],
])
def test_eodhd_actions_disabled_before_network_or_credentials(monkeypatch, argv, capsys):
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    with pytest.raises(SystemExit) as ex:
        main(argv)
    assert ex.value.code == 2
    assert "EODHD_DISABLED_NO_SUBSCRIPTION" in capsys.readouterr().err


def test_eodhd_dataset_cannot_reenter_normal_build_path(tmp_path, capsys):
    spec={
        "mode":"EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE",
        "as_of":"2026-11-05",
        "assets":[{"id":"TEST","prices_source":{"provider":"EODHD_EOD_PERSONAL_RESEARCH"}}]
    }
    file=tmp_path/"fixture_spec.json"
    file.write_text(json.dumps(spec))
    with pytest.raises(SystemExit):
        main(["build","--spec",str(file),"--output",str(tmp_path/"output")])
    assert not (tmp_path/"output").exists()
    assert "EODHD_DISABLED_NO_SUBSCRIPTION" in capsys.readouterr().err


def test_free_tiingo_ecb_cli_still_available(capsys):
    for command in ("tiingo-personal-collect","bind-ecb-fx",
                    "collect","screen","tactical","risk"):
        with pytest.raises(SystemExit) as ex:
            main([command,"--help"])
        assert ex.value.code == 0
        out = capsys.readouterr().out
        assert "EODHD_DISABLED_NO_SUBSCRIPTION" not in out
