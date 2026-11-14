"""Fail PR CI when architectural traceability metadata is missing."""
from __future__ import annotations

import os
import sys
from investresearch.architecture_governance import validate_event_file


def main() -> int:
    path = os.environ.get('GITHUB_EVENT_PATH')
    if not path:
        print('GITHUB_EVENT_PATH must be set for PR checks', file=sys.stderr)
        return 2
    errors = validate_event_file(path)
    for error in errors:
        print('::error::V3 governance: '+error, file=sys.stderr)
    if errors:
        print('Fill the Architecture, Requirements, Milestones and Change class fields in the PR body.',file=sys.stderr)
        return 1
    print('PR architecture metadata validated')
    return 0


if __name__ == '__main__':
    sys.exit(main())
