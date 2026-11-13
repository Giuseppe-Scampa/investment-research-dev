# V3 source-code receipt — additive release hardening (13 November 2026)

**Scope:** P0 engineering traceability only. The frozen V3 protocol JSON, V3 scoring, same-K statistic, null calibration, historical fold classification and all market-data assumptions remain unchanged.

## What changed

The public historical-validation-v3 command now writes a second file (suffix .code-receipt.json) beside its existing private original JSON report, under an ignored data/private directory. No source-price rows, personal holdings, broker documents or keys are included.

The receipt records:
- SHA-256 of the EXACT original report bytes (not normalized JSON);
- SHA-256 of every public Block B Python source file under src/investresearch, all config/backtest JSON files and pyproject.toml;
- SHA-256 of a canonical sorted map of path/digest pairs;
- frozen V3 protocol SHA-256 plus Git HEAD and tracked worktree cleanliness when .git exists;
- explicit trade_ready=false, predictive_edge_certified=false, source_code_signature_verified=false, source_data_licence_verified=false.

The companion independent private A checker reconstructs these hashes from its EXACT PINNED B checkout without invoking any B code. CI must reject modified report bytes, source modules, fake signature claims, and mismatched Git revisions.

Example local usage (both paths must be legitimate local original files and new report output under private data):

    PYTHONPATH=src python -m investresearch.research_cli historical-validation-v3 \
      --bundle data/private/AUTHORIZED_ORIGINAL_BUNDLE \
      --output data/private/NEW_V3_REPORT.json

Receipt: data/private/NEW_V3_REPORT.json.code-receipt.json

## Boundaries

- SHA-256 is an integrity checksum, NOT a digital signature.
- Git HEAD alone cannot prove source-vintage authenticity or market-data licences.
- This does not authenticate market prices, rights, corporate actions, PIT membership, delisting cashflows or fiscal status.
- Frozen V3 protocol and V1/V2 reports are not modified.
- No original market-data files or user-private inputs are committed.
- No broker connection, trade approval, Alpha claims, PR merge or historical privacy remediation results from this change.
