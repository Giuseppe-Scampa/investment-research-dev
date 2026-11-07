"""Verify PR traceability to canonical V3 architecture (offline, no API).

This is metadata enforcement, not an automated architecture-review substitute.
"""
from __future__ import annotations

import re
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def validate_pr_metadata(body: str, manifest: dict) -> list[str]:
    if not isinstance(body, str):
        return ["Missing pull request body"]
    problems = []

    def field(label: str) -> str:
        match = re.search(r'(?im)^\s*' + re.escape(label) + r':\s*(.*?)\s*$', body)
        return match.group(1) if match else ''

    version = field('Architecture')
    if version != manifest['current_version']:
        problems.append('Architecture field must match manifest.current_version')
    requirements = [x.strip() for x in field('Requirements').split(',') if x.strip()]
    if not requirements or any(x not in manifest['requirement_ids'] for x in requirements):
        problems.append('Requirements must contain at least one recognized R-###, comma-separated')
    if len(requirements) != len(set(requirements)):
        problems.append('Requirements must not repeat IDs')
    milestones = [x.strip() for x in field('Milestones').split(',') if x.strip()]
    if not milestones or any(x not in manifest['milestones'] for x in milestones):
        problems.append('Milestones must contain at least one recognized M#, comma-separated')
    if len(milestones) != len(set(milestones)):
        problems.append('Milestones must not repeat IDs')

    kind = field('Change class')
    if kind not in ('Implementation', 'Documentation', 'Architecture'):
        problems.append('Change class must be Implementation, Documentation or Architecture')
    if kind == 'Architecture':
        adr = field('ADR')
        version_change = field('Proposed version')
        if not re.fullmatch(r'ADR-\d{4}', adr):
            problems.append('Architecture changes require ADR: ADR-NNNN')
        if not re.fullmatch(r'V\d+\.\d+\.\d+', version_change):
            problems.append('Architecture changes require Proposed version: Vx.y.z')
        if version_change == manifest['current_version']:
            problems.append('Architecture change must propose a new version, not rewrite baseline')
    return problems


def validate_event_file(path: Path, manifest_path: Path | None = None) -> list[str]:
    metadata = json.loads((manifest_path or ROOT/'docs/architecture/manifest.json').read_text(encoding='utf-8'))
    event = json.loads(Path(path).read_text(encoding='utf-8'))
    pr = event.get('pull_request')
    if not isinstance(pr, dict):
        return ['Missing pull_request object in event payload']
    return validate_pr_metadata(pr.get('body'), metadata)
