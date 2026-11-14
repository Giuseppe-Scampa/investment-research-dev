"""Contract checks are strict but don't require external GitHub services."""
import json

from investresearch.architecture_governance import validate_event_file, validate_pr_metadata
from investresearch.cli import ROOT

MANIFEST=json.loads((ROOT/'docs/architecture/manifest.json').read_text(encoding='utf-8'))
VALID='''Architecture: V3.0.0
Requirements: R-001, R-004, R-005, R-012
Milestones: M1, M3
Change class: Implementation
'''


def test_existing_pr_governance_metadata_accepted():
    assert validate_pr_metadata(VALID,MANIFEST)==[]


def test_invalid_version_and_references_rejected():
    invalid=VALID.replace('V3.0.0','V3.1.0').replace('R-012','R-999').replace('M3','M7')
    errors=validate_pr_metadata(invalid,MANIFEST)
    assert len(errors)==3
    assert any('Architecture field' in x for x in errors)


def test_architecture_change_requires_adr_and_new_version():
    proposal=VALID.replace('Implementation','Architecture')
    assert len(validate_pr_metadata(proposal,MANIFEST))==2
    proposal+='ADR: ADR-0002\nProposed version: V3.1.0\n'
    assert validate_pr_metadata(proposal,MANIFEST)==[]
    proposal=proposal.replace('Proposed version: V3.1.0','Proposed version: V3.0.0')
    assert any('must propose a new version' in x for x in validate_pr_metadata(proposal,MANIFEST))


def test_missing_and_repeated_ids_rejected():
    assert any('Requirements' in x for x in validate_pr_metadata(VALID.replace('R-001, R-004, R-005, R-012',''),MANIFEST))
    assert any('repeat' in x for x in validate_pr_metadata(VALID.replace('R-001, R-004','R-001, R-001'),MANIFEST))
    assert any('Milestones' in x for x in validate_pr_metadata(VALID.replace('M1, M3',''),MANIFEST))


def test_pr_event_input_offline(tmp_path):
    event=tmp_path/'event.json'
    event.write_text(json.dumps({'pull_request':{'body':VALID}}),encoding='utf-8')
    assert validate_event_file(event)==[]
    event.write_text(json.dumps({'pull_request':{}}),encoding='utf-8')
    assert validate_event_file(event)
