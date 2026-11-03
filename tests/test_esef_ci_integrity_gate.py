"""Safety regression for live ESEF CI quality gate; no external downloads."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_live_esef_integrity_checks_are_not_silenced_by_continue_on_error():
    yaml = (ROOT / '.github/workflows/ci.yml').read_text()
    live = yaml.split("  live_esef_smoke:", 1)[1]
    edison, prysmian = live.split("  live_prysmian_esef_smoke:", 1)
    for block in (edison, prysmian):
        assert 'continue-on-error: true' not in block
        assert 'classification=VALIDATION_FAILED' in block
        assert 'SOURCE_UNAVAILABLE_NO_VALIDATION' in block
        assert 'NUMERIC_RECONCILIATION_PASSED_REVIEW_REQUIRED' in block
        assert 'exit 2' in block
        assert 'grep -Fq' in block


def test_production_probes_keep_actual_utc_retrieval_timestamps():
    # Unit-test-only clock patching must not rewrite the real-source timestamp.
    for script in ('smoke_edison_esef.py', 'smoke_prysmian_esef.py'):
        content = (ROOT / 'tools' / script).read_text()
        assert "'retrieved_at_utc':datetime.now(timezone.utc).isoformat()" in content.replace(" ", "")
        assert 'class SourceUnavailable' in content
        assert 'return 1' in content and 'return 2' in content


def test_multiline_ci_shell_steps_parse_with_bash():
    """Prevents orphaned fi/done and other shell syntax mistakes in CI YAML."""
    import subprocess

    lines = (ROOT / '.github/workflows/ci.yml').read_text().splitlines()
    scripts = []
    for index, line in enumerate(lines):
        if line.strip() != 'run: |' or not line.startswith('        run: |'):
            continue
        body = []
        for candidate in lines[index + 1:]:
            if candidate.strip() and not candidate.startswith('          '):
                break
            body.append(candidate[10:] if candidate.startswith('          ') else '')
        scripts.append('\\n'.join(body))
    assert len(scripts) >= 4
    for number, script in enumerate(scripts, 1):
        result = subprocess.run(['bash', '-n'], input=script, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f'CI multiline script {number}: {result.stderr}'
