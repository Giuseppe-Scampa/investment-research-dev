"""Synthetic offline Xetra CSV fixtures; never requests/downloads vendor data."""
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import pytest

from investresearch.research_xetra_universe import (
    PROVIDER, parse_xetra, write_xetra_candidates,
)

ASOF = date(2026, 11, 5)
OFFICIAL = ("https://www.cashmarket.deutsche-boerse.com/resource/blob/"
            "1528/0447d5f72a1ca9cd3f00a6bd5f8805cc/data/"
            "t7-xetr-allTradableInstruments.csv")
FIELDS = ["Product Status", "Instrument Status", "Instrument", "ISIN",
          "Mnemonic", "MIC Code", "Settlement Currency", "Instrument Type"]


def _row(isin, symbol, code, name="Synthetic Test Security", **changes):
    row = dict(zip(FIELDS, ["Active", "Active", name, isin, symbol,
                            "XETR", "EUR", code]))
    return {**row, **changes}


def _snapshot(rows, *, timestamp="04.11.2026", market="XETR", fields=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields or FIELDS,
                            delimiter=";", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return (f"Market: {market}\nDate Last Update: {timestamp}\n" +
            stream.getvalue()).encode("utf-8")


def _meta(raw, **changes):
    return {**{"provider": PROVIDER, "source_url": OFFICIAL,
               "sha256": hashlib.sha256(raw).hexdigest(),
               "retrieved_at_utc": "2026-11-05T09:05:00Z"}, **changes}


def _normal_rows():
    return [
        _row("US0378331005", "AAPL", "CS"),
        _row("IE00B4L5Y983", "WRLD", "ETF"),
        _row("JE00B1VS3333", "SLVR", "ETC"),
        _row("CH1135202120", "TEST", "ETN"),
        _row("DE000A2LQ2D0", "OLD", "CS", **{"Instrument Status": "PendingDeletion"}),
    ]


def test_official_multi_asset_reference_only_not_ucits_or_scores():
    raw = _snapshot(_normal_rows())
    rows, manifest = parse_xetra(raw, _meta(raw), as_of=ASOF)
    assert len(rows) == 4
    assert {row["asset_type"] for row in rows} == {
        "EQUITY", "ETF_LEGAL_STATUS_UNVERIFIED", "ETC", "ETN"}
    assert manifest["candidate_count"] == 4
    assert manifest["skipped_counts"] == {"NOT_ACTIVE": 1}
    assert manifest["source_type_counts"] == {"CS": 1, "ETC": 1, "ETF": 1, "ETN": 1}
    assert manifest["source_update_date"] == "2026-11-04"
    assert "No 61-session prices" in manifest["limitations"][3]
    for row in rows:
        assert row["status"].startswith("DISCOVERY_ONLY_")
        assert "price" not in row and "score" not in row and "tax" not in row


@pytest.mark.parametrize("update", [
    {"provider": "UNOFFICIAL"},
    {"sha256": "0" * 64},
    {"source_url": "https://evil.example/data/t7-xetr-allTradableInstruments.csv"},
    {"source_url": OFFICIAL + "?key=secret"},
    {"retrieved_at_utc": "2026-11-06T00:00:00Z"},
    {"retrieved_at_utc": "2026-11-05T10:00:00+01:00"},
    {"encoding": "utf-16"},
])
def test_metadata_provenance_fail_closed(update):
    raw = _snapshot(_normal_rows())
    with pytest.raises(ValueError):
        parse_xetra(raw, _meta(raw, **update), as_of=ASOF)


@pytest.mark.parametrize("raw", [
    _snapshot(_normal_rows(), timestamp="06.11.2026"),
    _snapshot(_normal_rows(), market="XFRA"),
    _snapshot([_row("INVALID123456", "ABC", "CS")]),
    _snapshot([_row("US0378331005", "ABC", "CS",
                    **{"MIC Code": "XFRA"})]),
    _snapshot([_row("US0378331005", "ABC", "CS")] * 2),
    _snapshot([_row("US0378331005", "ABC", "CS",
                    **{"Instrument Status": "Published"})]),
    _snapshot([_row("US0378331005", "ABC", "CS")],
              fields=[x for x in FIELDS if x != "ISIN"]),
])
def test_malformed_or_unusable_snapshots_rejected(raw):
    with pytest.raises(ValueError):
        parse_xetra(raw, _meta(raw), as_of=ASOF)


def test_unrecognized_category_is_not_misclassified_as_certificate():
    raw = _snapshot([_row("US0378331005", "ABC", "WAR"),
                     _row("JE00B1VS3333", "XYZ", "FUTURE_TYPE")])
    rows, manifest = parse_xetra(raw, _meta(raw), as_of=ASOF)
    assert len(rows) == 1
    assert rows[0]["asset_type"] == "WARRANT_CERTIFICATE_STATUS_UNVERIFIED"
    assert manifest["skipped_counts"] == {"UNKNOWN_INSTRUMENT_TYPE": 1}


def test_local_private_only_writes_with_checksums_and_formula_escape(tmp_path):
    raw = _snapshot([_row("US0378331005", "ABC", "CS", name="=FICTITIOUS()")])
    source = tmp_path / "source.csv"
    source.write_bytes(raw)
    evidence = tmp_path / "source_meta.json"
    evidence.write_text(json.dumps(_meta(raw)), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="data/private"):
        write_xetra_candidates(source, evidence, ASOF, repo / "tracked", repo_root=repo)
    out = repo / "data" / "private" / "xetra"
    result = write_xetra_candidates(source, evidence, ASOF, out, repo_root=repo)
    assert result["candidate_count"] == 1
    csv_bytes = (out / "XETRA_UNRANKED_CANDIDATES.csv").read_bytes()
    assert b"'=FICTITIOUS()" in csv_bytes
    saved = json.loads((out / "XETRA_DISCOVERY_MANIFEST.json").read_text())
    assert saved["candidate_csv_sha256"] == hashlib.sha256(csv_bytes).hexdigest()
    assert str(tmp_path) not in json.dumps(saved)
    assert raw not in csv_bytes
    with pytest.raises(ValueError, match="already populated"):
        write_xetra_candidates(source, evidence, ASOF, out, repo_root=repo)


def test_cli_offline_xetra_command(tmp_path):
    from investresearch.research_cli import main

    raw = _snapshot(_normal_rows())
    source = tmp_path / "snapshot.csv"
    source.write_bytes(raw)
    meta = tmp_path / "metadata.json"
    meta.write_text(json.dumps(_meta(raw)), encoding="utf-8")
    output = tmp_path / "research"
    main(["xetra-universe", "--raw", str(source), "--metadata", str(meta),
          "--as-of", ASOF.isoformat(), "--output", str(output)])
    assert json.loads((output / "XETRA_DISCOVERY_MANIFEST.json").read_text())["candidate_count"] == 4
