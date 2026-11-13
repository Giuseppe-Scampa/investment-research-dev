"""Additive, independent code snapshot receipt for the frozen V3 backtest.

Does not modify the original V3 JSON/protocol or score. SHA-256 binds a
private report to the exact public B source bytes, but is not an author
signature, a market-data licence, or proof of predictive performance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

SCHEMA = "B_V3_SOURCE_CODE_RECEIPT_V1"
PROTOCOL_REL = "config/backtest/v3_long_horizon_protocol_v3_2026-11-11.json"
REPORT_SCHEMA = "V3_LONG_HORIZON_BACKTEST_V3"
MAX_REPORT_BYTES = 4_000_000
MAX_CODE_BYTES = 2_000_000
MAX_CODE_FILES = 350
REQUIRED_CODE = {
    "src/investresearch/research_historical_validation_v3.py",
    "src/investresearch/research_historical_validation_v2.py",
    "src/investresearch/research_historical_validation.py",
    "src/investresearch/research_screen.py",
    "src/investresearch/research_negative_control_v3.py",
    "src/investresearch/research_slippage_v3.py",
    "src/investresearch/research_outcome_diagnostics_v3.py",
    PROTOCOL_REL,
}


def _private_output(path: Path) -> bool:
    parts = path.parts
    return any(parts[i] == "data" and parts[i + 1] == "private"
               for i in range(len(parts) - 1))


def _source_map(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Block B repository root must be a real directory")
    source = root / "src" / "investresearch"
    config = root / "config" / "backtest"
    if not source.is_dir() or not config.is_dir():
        raise ValueError("Missing Block B original code or frozen protocol directory")
    files = [*source.rglob("*.py"), *config.glob("*.json"), root / "pyproject.toml"]
    paths = {}
    if len(files) > MAX_CODE_FILES:
        raise ValueError("Unbounded code tree")
    for f in files:
        if f.is_symlink() or not f.is_file() or f.stat().st_size > MAX_CODE_BYTES:
            raise ValueError("Source code must be a bounded regular file, not a symlink")
        rel = f.relative_to(root).as_posix()
        if rel in paths:
            raise ValueError("Duplicated source path")
        paths[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    if not REQUIRED_CODE.issubset(paths):
        raise ValueError("Expected primary V3 modules are missing")
    return dict(sorted(paths.items()))


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _git_provenance(root: Path) -> tuple[str | None, bool | None]:
    """A source archive may lack .git; never fabricate its revision."""
    try:
        head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"],
                              cwd=root, capture_output=True, text=True,
                              timeout=3, check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                cwd=root, capture_output=True, text=True,
                                timeout=3, check=True).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None, None
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        return None, None
    return head, not bool(status.strip())


def make_receipt(report_path: Path, repo_root: Path) -> dict:
    root = Path(repo_root).absolute()
    report_path = Path(report_path).absolute()
    if report_path.is_symlink() or not report_path.is_file():
        raise ValueError("Original V3 report must be a regular existing file")
    report_path = report_path.resolve(strict=True)
    if not _private_output(report_path) or not 0 < report_path.stat().st_size <= MAX_REPORT_BYTES:
        raise ValueError("V3 report must be a bounded private data file")
    report_raw = report_path.read_bytes()
    report = json.loads(report_raw)
    if (not isinstance(report, dict) or
            report.get("schema_version") != REPORT_SCHEMA or
            report.get("trade_ready") is not False or
            report.get("predictive_edge_certified") is not False):
        raise ValueError("Not an unmodified non-executable V3 research report")
    originals = _source_map(root)
    protocol = (root / PROTOCOL_REL).read_bytes()
    protocol_sha = hashlib.sha256(protocol).hexdigest()
    if report.get("preregistered_protocol_sha256") != protocol_sha:
        raise ValueError("Report protocol does not match current immutable V3 source")
    code_head, clean = _git_provenance(root)
    return {
        "schema_version": SCHEMA,
        "receipt_scope": "CODE_BYTES_AND_REPORT_BYTES_ONLY_NO_MARKET_OR_TAX_CERTIFICATION",
        "report_sha256": hashlib.sha256(report_raw).hexdigest(),
        "registered_protocol_sha256": protocol_sha,
        "source_code_sha256": originals,
        "source_tree_sha256": hashlib.sha256(_canonical(originals)).hexdigest(),
        "source_file_count": len(originals),
        "git_head_sha": code_head,
        "git_tracked_worktree_clean": clean,
        "source_code_signature_verified": False,
        "source_data_licence_verified": False,
        "predictive_edge_certified": False,
        "trade_ready": False,
    }


def write_receipt(report_path: Path, *, repo_root: Path) -> Path:
    report_path = Path(report_path).absolute()
    result = make_receipt(report_path, repo_root)
    output = report_path.with_name(report_path.name + ".code-receipt.json")
    if output.exists() or output.is_symlink() or not _private_output(output):
        raise ValueError("Refusing overwrite or non-private V3 code receipt")
    payload = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(output, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
    except BaseException:
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return output
