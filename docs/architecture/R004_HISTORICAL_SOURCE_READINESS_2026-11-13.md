# P0: first source-readiness gate for frozen V3 historical validation
Date: 13 November 2026. Applies to public Block B, experimental branch.

## What was actually implemented

1. `research_bundle.build_bundle` retains explicitly provided
   `listing_date` and `delisted_date` in the original SHA-verified
   manifest. This fixes the prior loss of lifecycle dates between the
   source input and the backtest evaluator. The dates MUST be exact ISO
   calendar days, and delisting cannot precede listing. A missing date
   is left missing: it is **never** inferred from first/last price.
2. `investresearch-b historical-source-readiness` inspects existing local
   bundle bytes and the **unaltered frozen V3** schedule. For each
   source-asserted active listing/anchor pair, it checks exact
   exchange-calendar 61 preceding sessions and 31 subsequent sessions.
   Unmatured future paths and matured but missing sessions are kept
   separate. Aggregates only; no symbol/ISIN, price, performance or holdings.
3. Original source SHA-256 is checked by the existing bundle loader;
   the new audit additionally binds its report to the original manifest
   bytes and frozen V3 protocol SHA-256.
4. No new paid market-data service, broker integration, source
   scraping, strategy, tax rule, model score, null threshold or backtest
   protocol is introduced. All reports remain **NOT TRADE READY**.

## How to use with a real authorized historical bundle

The original local source must already have been acquired in compliance
with terms and normalized using the project's existing reviewed
Euronext/FWB/ECB importers. The audit does NOT acquire data.

Run from the B repository on a new ignored private output path:

    mkdir -p data/private
    investresearch-b historical-source-readiness \
      --bundle data/private/EXISTING_ORIGINAL_BUNDLE \
      --output data/private/NEW_HISTORICAL_READINESS.json

The result is an aggregate JSON. Key fields:
- `unknown_listing_date_count`: source records lacking even a
  *source-declared* historic listing start; this is not a proxy for
  genuine PIT eligibility.
- `member_anchor_combinations_with_complete_61_day_history`;
- `member_anchor_combinations_with_matured_complete_31_day_path`;
- `member_anchor_combinations_with_matured_unresolved_31_day_path`;
- `member_anchor_combinations_with_forward_path_not_yet_matured`;
- `usd_fx_source_missing`, `unsupported_v3_price_basis_or_provider`.
- Per-anchor aggregates, no underlying security identifiers.

**Critical qualification**: missing `delisted_date` is normal for a
currently traded stock; it does NOT certify a historical panel includes
companies that later disappeared. A reported listing or delisting
date is **operator/source asserted**, not an authenticated,
timestamped corporate action or issuer identity. With the currently
available inputs, the audit ALWAYS reports
`BLOCKED_SOURCE_EVIDENCE_AND_POINT_IN_TIME_INCOMPLETE`.

This is an independent source **diagnostic**, not a replacement for the
V3 preregistered statistical gate, and not proof that a full panel
avoids survivorship bias. It does not infer missing dividends, splits,
rights issues, delisting cashflows, market-price licences or tax
status; no outputs are certified merely from full calendar coverage.

## Regressions added

Synthetic-only tests ensure:
- optional listing fields survive bundle normalization;
- absent dates are not inferred from a complete price history;
- invalid chronology or date formats fail during original import;
- absent matured futures do not disappear from coverage;
- tampering with the original normalized price bytes is rejected;
- private-only output is never overwritten and CLI output is aggregate.

## Remaining real-source P0 blockers

1. Licensed, original historical **PIT identity and universe membership**
   including delisted companies and ticker reuse, with source vintages.
2. Exchange-verified corporate actions, dividends, subscription rights,
   relevant delisting settlement cashflows and market-price provenance.
3. At least the protocol's required 30 independent V3 folds, >=20
   independently eligible instruments per fold and mature outcomes.
4. Existing bank statements, exact per-ISIN fiscal category, commission
   schedule and calendar must still be verified separately in private A.

Only a genuinely new, independent unseen holdout or future prospective
paper ledger can justify positive predictive certification. The
current exploratory historical TOP2 underperformance vs same-K cannot be
relabelled as proof of a winning strategy.
