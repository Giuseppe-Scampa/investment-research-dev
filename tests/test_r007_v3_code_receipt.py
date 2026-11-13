"""Original byte provenance tests on FICTIONAL inputs only."""
import hashlib
import json

import pytest

from investresearch.research_v3_code_receipt import (
    REQUIRED_CODE, make_receipt, write_receipt,
)


def _fixture(tmp_path):
    root = tmp_path / "fictional_block_b"
    for rel in REQUIRED_CODE:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# FICTIONAL module\n" if path.suffix == ".py" else '{"fake":true}\n')
    (root / "pyproject.toml").write_text("[project]\nname='fake'\n")
    protocol = root / "config/backtest/v3_long_horizon_protocol_v3_2026-11-11.json"
    report = tmp_path / "data/private/V3_FICTIONAL.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({
        "schema_version": "V3_LONG_HORIZON_BACKTEST_V3",
        "preregistered_protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "trade_ready": False,
        "predictive_edge_certified": False,
        "fictional_data_only": True,
    }))
    return root, report


def test_code_receipt_keeps_original_report_identical_and_is_private(tmp_path):
    root, report = _fixture(tmp_path)
    original = report.read_bytes()
    receipt = write_receipt(report, repo_root=root)
    obj = json.loads(receipt.read_text())
    assert report.read_bytes() == original
    assert obj["report_sha256"] == hashlib.sha256(original).hexdigest()
    assert obj["source_file_count"] == len(REQUIRED_CODE) + 1
    assert obj["source_code_signature_verified"] is False
    assert obj["trade_ready"] is False
    with pytest.raises(ValueError, match="overwrite"):
        write_receipt(report, repo_root=root)


def test_code_change_makes_new_snapshot_digest(tmp_path):
    root, report = _fixture(tmp_path)
    before = make_receipt(report, root)
    file = root / "src/investresearch/research_screen.py"
    file.write_text(file.read_text() + "# version changed\n")
    after = make_receipt(report, root)
    assert after["source_tree_sha256"] != before["source_tree_sha256"]
    assert after["report_sha256"] == before["report_sha256"]


def test_forged_trade_ready_or_protocol_blocked(tmp_path):
    root, report = _fixture(tmp_path)
    obj = json.loads(report.read_text())
    obj["trade_ready"] = True
    report.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="non-executable"):
        make_receipt(report, root)
    obj["trade_ready"] = False
    obj["preregistered_protocol_sha256"] = "0" * 64
    report.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="protocol"):
        make_receipt(report, root)


def test_non_private_output_or_symlink_source_blocked(tmp_path):
    root, report = _fixture(tmp_path)
    public = tmp_path / "public.json"
    public.write_bytes(report.read_bytes())
    with pytest.raises(ValueError, match="private"):
        make_receipt(public, root)
    module = root / "src/investresearch/research_screen.py"
    source = root / "src/investresearch/source.txt"
    module.rename(source)
    module.symlink_to(source)
    with pytest.raises(ValueError, match="symlink"):
        make_receipt(report, root)
