"""Architecture version guard; milestone names must not silently disappear."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'docs/architecture/manifest.json'


def test_architecture_manifest_has_unique_stable_ids():
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert m['schema_version']=='architecture-control-v1'
    assert m['current_version']=='V3.0.0'
    assert m['milestones']==['M1','M2','M3','M4','M5','M6']
    assert len(set(m['requirement_ids']))==len(m['requirement_ids'])==13
    assert m['requirement_ids']==[f'R-{i:03d}' for i in range(1,14)]
    assert m['version_change_requires']=='ADR-and-user-approval'


def test_architecture_paths_and_requirement_matrix_are_in_sync():
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    for key in ('baseline_path','index_path','roadmap_path',
                'change_control_path','review_prompts_path'):
        assert (ROOT/m[key]).is_file(), key
    assert all((ROOT/p).is_file() for p in m['decision_register'])
    baseline=(ROOT/m['baseline_path']).read_text(encoding='utf-8')
    index=(ROOT/m['index_path']).read_text(encoding='utf-8')
    roadmap=(ROOT/m['roadmap_path']).read_text(encoding='utf-8')
    assert m['current_version'] in baseline and m['current_version'] in index
    for milestone in m['milestones']:
        assert f'**{milestone}**' in baseline, milestone
    for rid in m['requirement_ids']:
        assert rid in baseline and rid in roadmap, rid
    assert 'AI gratuita' in baseline
    assert 'Research Engine permanente' in baseline


def test_architecture_review_prompts_are_independent_and_actionable():
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    prompts=(ROOT/m['review_prompts_path']).read_text(encoding='utf-8')
    assert 'Prompt A — Claude' in prompts
    assert 'Prompt B — Gemini' in prompts
    assert 'NON VERIFICATO' in prompts
    assert 'non è un prerequisito' in prompts or 'NON un prerequisito' in prompts or 'non sono un prerequisito' in prompts
    assert 'R-001' in prompts and 'R-013' in prompts
    assert 'Critical path' in prompts or 'Critical path' in prompts.lower().title()
