# R-004/R-005 → R-007: one original-source USA + EU research universe

**Software increment (7 November 2026):** original Tiingo US and Deutsche
Börse FWB Xetra EUR history files can be combined into one B market-research
bundle. A new **private A one-command runner** can then bind original ECB FX,
rebuild B's provenance-checked dataset and execute the existing private
Decision Engine, including full B→A funnel/risk/valuation/audit dashboard.

This is an offline workflow. **No EODHD subscription, web scraping, quote
download, paid API or automatic order.** Operator-asserted source rights
and vendor adjustments are not independent certification.

## What the data owner must have acquired independently

- For each US instrument: the original Tiingo Personal daily EOD
  payload and its corresponding single-security `BUNDLE_INPUT_SPEC.json`
  from the existing explicit Tiingo collector, with personally reviewed ISIN,
  ticker, exchange, asset legal type and source terms.
- For each European Xetra instrument: the original manually downloaded
  FWB `Price History` CSV plus the one-security JSON matching
  `config/fwb_price_history_manual_example.json`. Record the original
  page, exact ISIN, UTC acquisition timestamp, SHA-256, locale/columns
  and all corporate-action adjustment checkbox selections.
- When **any** US/USD instrument is included, the original dated ECB
  EUR/USD history file and its SHA-256-bearing metadata, as used by the
  existing `bind-ecb-fx` command.
- All original files must be permitted for the intended personal/noncommercial
  analysis. Corporate actions, issuer identity, adjusted prices and tax status
  still need independent validation for an actual financial decision.

## Single command in PRIVATE A

Inside the private repository clone, keep original specs, ECB metadata
and any original SEC/ESEF/ABC files under ignored `data/private`.

```bash
PYTHONPATH=src python tools/run_mixed_source_decision2026.py \
  --block-b-root ../investment-research-dev \
  --source-spec data/private/us/EXAMPLE_BUNDLE_INPUT_SPEC.json \
  --source-spec data/private/eu/EXAMPLE_FWB_SPEC.json \
  --ecb-meta data/private/ecb/ECB_ORIGINAL_META.json \
  --output data/private/MY_NEW_SOURCE_RUN
```

To add additional instruments, repeat `--source-spec` (up to 500), always
with the **same as-of date**. No ISIN or source file can be repeated.
The number 500 is a software safety cap, **not** a promise of market-source
availability or free-tier quota.

Optional private inputs (only after original sources are available):
`--annual-links`, `--annual-sec-report`, `--annual-eu-report`,
`--private-abc-case`. The broker case must have the same `as_of`.
Without any USD input, omit `--ecb-meta`.

The runner invokes an allowlist of **offline** B CLI commands through a
sanitized process environment, never forwards API secrets, and produces:
- `source/MIXED_ORIGINAL_SOURCES.json`: original-source-referencing spec.
- `source/MIXED_WITH_ORIGINAL_ECB_FX.json` when USD is present.
- `bundle/manifest.json`: normalized, SHA-checked originals (not new prices).
- `integrated/INTEGRATION_READINESS.json`: A's private decision gate.
- `integrated/INTEGRATION_DASHBOARD.html`: narrative and coverage.
- `integrated/INTEGRATED_DECISION_LEDGER.json`: original evidence digests.
- `PRIVATE_SOURCE_TO_DECISION_AUDIT.json`: source/spec/FX readiness digests.

Every artifact under a repository is private-only, no original market
payload or private portfolio report is automatically published to GitHub.
The output is **not a trade suggestion or an executable price**.

## CI, source readiness and limitations

The exact end-to-end code path is tested through
`tools/generate_mixed_crossrepo_fixture.py` on entirely made-up Tiingo,
FWB and ECB-schema observations. It requires explicit `TEST_ONLY_*` and
`NOT_MARKET_DATA_*` labels on the synthetic fixtures and independent A
assertions that the result remains `fixture_only=true` and
`trade_ready=false`.

**This confirms programming/integration only.** M3/M4 DONE still require
independently licensed, dated, audited price histories for an authentic broad
US+EU universe (and compatible ETC/ETN/certificate coverage if claimed),
actual historical split/dividend verification and one evidenced 200+ candidate
funnel. New local FWB files require manual acquisition and terms review.
Restricted-source bytes must never be committed to public repositories.

The complete benchmark remains the immutable V3.0.0 baseline and M1–M6/R-001
through R-013 acceptance matrix. No requirements are removed or silently
promoted to DONE.
