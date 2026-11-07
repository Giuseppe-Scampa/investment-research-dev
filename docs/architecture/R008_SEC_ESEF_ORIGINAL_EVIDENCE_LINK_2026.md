# R-008 — original SEC/ESEF issuer facts ↔ source-screened instrument

**Software state:** producer and private consumer implemented, tested against
fictional real-schema inputs and a genuinely executed B→A synthetic full stack.
**Operational state:** data, identities, accounting facts and rights not
independently authenticated. No live real-issuer example is accepted as final.

## Why this bridge exists

B already collects official SEC companyfacts and audits locally acquired
European ESEF/XHTML reports. Previously those accounting audits did not follow
a particular point-in-time instrument ID into the permanent funnel and A
decision dashboard. This module adds an **optional provenance overlay**
without assuming that a public SEC ticker establishes a valid ISIN.

Never use an SEC ticker-only join to infer an ISIN. For each eligible EQUITY,
a human/independent-source link must include the exact **B security id,
12-digit valid ISIN, SEC ticker and 10-digit CIK**, or **B id, ISIN and
original EU annual report id**. The identity remains operator asserted until
the original issuer/exchange evidence is confirmed separately.

## Original source files and invocation

Use original bounded local outputs:
- `SEC_ANNUAL_RESEARCH.json` from B `sec-pilot` (official SEC current
  ticker/catalog + SEC EDGAR companyfacts; independent market ISIN crosswalk
  **not** provided by SEC).
- `EU_REPORT_COVERAGE.json` from B `eu-filings --extract-ifrs`
  (original ESEF/PDF bytes and publication evidence, not an audit of facts).
- `config/annual_original_source_links_example.json` copied privately and
  edited to bind the exact B screening and source identifiers.

```bash
# Output MUST remain under ignored private data for real external inputs
investresearch-b screen --bundle data/private/REAL_SOURCE_BUNDLE \
  --output data/private/research-screen

# Compute the SHA-256 of canonical JSON (NOT of pretty-printed raw file bytes):
python - <<'PY'
from pathlib import Path
import json
from investresearch.research_fundamentals_link import _digest
p=Path('data/private/research-screen/BLOCK_B_SCREENING.json')
print(_digest(json.loads(p.read_text())))
PY

investresearch-b annual-fundamentals \
  --bundle data/private/REAL_SOURCE_BUNDLE \
  --identity-links data/private/ANNUAL_LINKS.json \
  --sec-report data/private/SEC_ANNUAL_RESEARCH.json \
  --eu-report data/private/EU_REPORT_COVERAGE.json \
  --output data/private/annual-issuer-evidence
```

Only one of `--sec-report` or `--eu-report` is necessary, but at least one
must exist. `as_of` must match the screened bundle and supplied evidence.
No network, AI, broker account or paid API is invoked. Unmatched, future,
ambiguous, non-equity, inconsistent margin or source-URL/CIK identities are
rejected; no source is re-attributed silently. Original SEC annual reported
numbers are kept with their specific filing and original companyfacts digest.
ESEF annual output is **candidate coverage only**: unresolved iXBRL concepts
are not passed as verified revenue, EBITDA or FCF.

The private A integration accepts:
`--annual-links`, `--annual-sec-report`, `--annual-eu-report` alongside
`--block-b-root`, `--bundle` and `--output`. All three original source
files must reside within A's ignored `data/private`. A independently checks
provenance hash, issuer identity, published dates, SEC margin arithmetic,
count completeness and locked no-ranking/no-tax/no-trade flags. A adds
`annual/RESEARCH_ANNUAL_FACTS.json` to the SHA-256 decision ledger and
displays SEC/ESEF coverage in the local dashboard.

**Critical:** annual revenue/margin coverage is not equity valuation.
Market capitalization, shares, enterprise value, free cash flow and effective
financial reporting units still need separately authenticated, dated sources.
This module does not automatically turn SEC or ESEF issuer evidence into
buy candidates, trade recommendations or fiscal realizations.

## Remaining external acceptance gates

- A legitimate original SEC companyfacts pilot and original ESEF reports with
  publication timestamps and source references.
- An independently documented ISIN/CIK/ticker/venue or EU report ISIN link.
- Reconciliation against filed PDF/XHTML accounting scope, iXBRL contexts,
  units and audit date (including restatement/lookahead checks).
- Legally authorized source usage and 61+ genuine adjusted historical prices
  where relevant.
- A private B→A full-stack run on real sources, reviewed without exposing
  personal/broker information.

The 2-issuer integration CI uses `tools/generate_annual_crossrepo_fixture.py`,
which generates entirely invented SEC source numbers and digests. **It is not
evidence of real source accuracy or investment suitability.**
