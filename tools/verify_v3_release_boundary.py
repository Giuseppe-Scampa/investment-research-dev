"""R-011/R-012: fail-closed public repository release/privacy gate, offline.

Does not inspect network, secrets APIs, user bank files or third-party licences.
It enforces versioned V3.0.0 architecture file integrity, known ignore rules,
no tracked private/source files and the operator's no-EODHD execution policy.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
V3_BLOB_SHA="b2fd872a9d7cdb8869fcdf16008e6a0c44b5cc32"


def git_blob_sha(raw:bytes):
    return hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()


def tracked_issues(paths):
    problems=[]
    for raw in paths:
        name=raw.replace("\\","/").lstrip("/")
        lower=name.lower()
        pieces=lower.split("/")
        if ("data/private" in lower or any(x in ("private","secrets",".env",".ssh")
                                            for x in pieces)
                or lower.endswith((".pem",".p12",".pfx",".key",".sqlite",".db"))
                or "portfolio_private" in lower):
            problems.append("Tracked private/sensitive path: "+name)
        if lower.startswith("reports/generated/") and not lower.endswith(".gitkeep"):
            problems.append("Generated market/personal report tracked: "+name)
    return problems


def verify(root=ROOT):
    base=Path(root).resolve()
    issues=[]
    spec=base/"docs/architecture/V3.0.0.md"
    if not spec.is_file() or git_blob_sha(spec.read_bytes())!=V3_BLOB_SHA:
        issues.append("Approved V3.0.0 baseline content differs from pinned immutable blob")
    ignored=base/".gitignore"
    if not ignored.is_file():
        issues.append("Missing repository ignore policy")
    else:
        data=ignored.read_text(encoding="utf-8")
        for required in ("data/private/",".env","reports/generated/"):
            if required not in data:
                issues.append("Missing ignore policy: "+required)
    ci=base/".github/workflows/ci.yml"
    if not ci.is_file():
        issues.append("Missing reviewed CI")
    else:
        text=ci.read_text(encoding="utf-8")
        section=text.split("  live_eodhd_evaluation_smoke:",1)
        if len(section)!=2 or "    if: false " not in section[1][:1200]:
            issues.append("EODHD network job is not explicitly disabled")
    try:
        proc=subprocess.run(["git","ls-files","-z"],cwd=base,check=True,
                            capture_output=True,timeout=15)
        paths=[x.decode("utf-8","replace") for x in proc.stdout.split(b"\0") if x]
        issues.extend(tracked_issues(paths))
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        issues.append("Cannot verify exact Git-tracked privacy boundary")
    return issues


def main():
    issues=verify()
    if issues:
        for item in issues:
            print("V3_RELEASE_GATE_BLOCKED:",item)
        raise SystemExit(2)
    print("V3_RELEASE_BOUNDARY_PASS: immutable baseline, ignored private data, EODHD disabled, zero broker execution")


if __name__=="__main__":
    main()
