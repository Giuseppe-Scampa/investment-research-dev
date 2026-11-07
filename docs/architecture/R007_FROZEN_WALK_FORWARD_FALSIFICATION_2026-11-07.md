# R-007/R-008 — Pre-registered historical falsification, 2026

**Registered before viewing outcomes:** commit
`8755eb8821b9b0a9f6fe26140c39e67cf5c211c6`.
**Exact frozen protocol:** `config/backtest/v3_2026_fixed_protocol.json`,
SHA-256 `e2ce1ba5928218c2ff78b7962058e7f862713226ff51ef574be5aac8617a26d2`.
The evaluator checks this digest and the unchanged B rank weights; any
change requires an explicitly new protocol/version. Do not optimize the
candidate score or testing window against held-out performance.

## Question that can fail

Does **TOP 2 by existing B source-checked score at decision date T**
produce excess return over a costed equal-weight, as-of eligible universe,
a fixed cash return (0%, not a deposit forecast) and 10,000 random
two-asset portfolios drawn from the **same frozen eligible set**? A
selection with positive raw return can lose to all three comparators.
No output labels performance confirmed unless returns are reconstructed
from licensed and independently checked **actual original** price sources.

A false historical positive is more harmful than no result.

## Frozen experiment

- **Universe:** eligible current B supported equities, UCITS ETFs,
  ETCs and ETNs; never certificate payoff, unverifiable oil exposure,
  unsuitable raw/unadjusted or interrupted price history. For the
  retrospective experiment only, B accepts FWB and Euronext original
  manually obtained adjusted daily CSV. US Tiingo Starter does **not**
  authorize a persistent backtest archive under ToS 1.6(a).
- **Calendar scope:** dated 2026 exchange holiday sets only, decision
  anchors April–September every 45 calendar days moved backward to
  a common validated session. No extrapolation to 2022–2025 or 2027:
  a new independently validated pluriennial calendar and newly registered
  multiyear protocol would be required.
- **Information set at T:** the same production `_score_indicators`
  and `_market_score` (0.30/0.20/0.20/0.15/0.15) use <=T rows only;
  61 consecutive prior exchange sessions are required. The raw price
  schema is strictly date, close, volume; a forward-return canary
  field is rejected. No post-T financial disclosures are admitted as
  factors.
- **Outcomes:** buy at next exchange-session EOD close **proxy**,
  sell after 30 subsequent close-to-close return intervals, reject a
  fold if **any** as-of-eligible symbol lacks the full future path or
  shows an unresolved >=15% daily corporate-action-like jump. Folds
  must not overlap. This does not simulate live intraday liquidity,
  settlement, slippage or executable quotes.
- **Costs:** fixed illustrative EUR 10,000 notional, each leg equal
  weighted; buy + sell 0.19% commission, minimum EUR 7 each side,
  and 0.25% FX each side if USD. These are a **scenario**, not
  independently verified bank records. Taxes are intentionally
  excluded in public B: require private per-ISIN classification,
  a certified realized gain/loss event and broker netting before
  calling any return after-tax. All comparisons apply the same
  two-position cost burden to the selected and random controls;
  the N-leg entire-universe comparator shows its own higher
  minimum-fee drag.
- **Results:** out-of-fold Spearman rank IC, mean excess vs equal
  universe, cash, share of picks above the eligible-universe
  median, selected-window drawdown, 10,000 fixed-seed random
  two-asset cohorts, bootstrap **whole independent folds**
  10,000 draws for 95% IC/excess CIs.
- **Predictive diagnostic gate (never forecast certification):**
  >=20 eligible symbols per independent fold, >=10 non-overlapping
  complete folds, lower endpoints of both IC and excess 95% CIs >0
  and random percentile >=90. Otherwise: *no evidence*.
  Multiple comparisons, market-regime extrapolation and sample
  representativeness require further prospective paper validation.

## What the existing CI actually demonstrated

The CI executes exact code over **six entirely invented 2026 price
paths**, including a deliberately adverse momentum reversal, using
10,000 simulated randomized two-position portfolios and 10,000
fold-bootstraps. Observed illustrative aggregates are:
- Synthetic persistent trend: 3 independent folds, excess vs equal
  universe +0.03886032, IC 1.0, 99.99th percentile of random portfolios.
- Synthetic adversarial regime: 3 folds, excess +0.00883049,
  IC 0.27602622, 68.06th percentile random. Some selected trades
  and folds lose money or underperform; experiment **fails** the
  random percentile and independence-power criteria.

The label `SYNTHETIC_NOT_MARKET_EVIDENCE` is retained in every result.
The test suite also verifies future append invariance, rejected
future-return columns, post-selection missing-outcome full-fold
rejection, 3:2/4:3/5:4 unadjusted split-like jumps, private file
permissions, unknown exposure and tax/no-trade false flags. None
of these results measure actual instruments' 2026 returns.

## How to run, once ORIGINAL authorized data exists

```bash
# Public B checkout: only previous source-verified private FWB/Euronext bundles.
investresearch-b historical-validation \
  --bundle data/private/SOURCE_BOUND_REAL_BUNDLE \
  --output data/private/NEW_HISTORICAL_VALIDATION.json

# Alternative: from private A checkout with original source specs.
PYTHONPATH=src python tools/run_mixed_source_decision2026.py \
  --block-b-root ../investment-research-dev \
  --source-spec data/private/milan/MILAN_SPEC.json \
  --source-spec data/private/paris/PARIS_SPEC.json \
  --source-spec data/private/xetra/XETRA_SPEC.json \
  --historical-validation \
  --output data/private/NEW_INTEGRATED_PRIVATE_RUN
```

Private A independently verifies the original B manifest hash, this
frozen protocol, unchanged no-tax/no-trade statuses, exactly identified
instruments, non-overlapping selection windows and the original output
SHA before writing its private audit.

**Current BLOCKER:** no such legally usable 90+ consecutive dated
original price sessions for several real symbols have been provided.
Even one real limited trial cannot meet 10 independent folds and
20 instruments with the 2026-only calendar. The engine cannot certify
market-data identity, corporate-action adjustment or source terms
from an operator assertion.

## Additional testing methods and gating

1. Point-in-time **snapshot parity**: truncate vendor source to T,
   compare score and select IDs against full file evaluated as T.
2. **Future-return canary**: a synthetic forward-return column or a
   financial fact filed after T must never enter feature computation.
3. **Corporate actions**: original vs adjusted split/dividend/rights
   series, reconcile 5–10 ISINs against a different licensed source.
4. **Metamorphic/invariance tests**: shuffled input ordering, renaming,
   duplicated dates, currency conversion, fee monotonicity and total
   original SHA-based provenance.
5. **Mutation testing**: disable missing-session, 15%-jump, unverified
   exposure, invalid-ISIN and future-source gates; tests must fail.
6. **Fault injection**: rate-limit/empty file/CSV locale mismatch,
   insufficient dates, missing FX, revised filings and delisted
   stocks must produce a review or blocked result, never fabricated
   zero returns.
7. **Independent fiscal calibration**: reconcile anonymized private
   historical bank executions with per-ISIN tax recognition, costs,
   withholding and actual FX.
8. **Prospective paper ledger**: freeze today's shortlist + original
   source SHA before seeing later prices; check prices and costed
   comparators after 30 sessions. This will be the only genuinely
   future out-of-sample check; no background job is implied unless
   explicitly scheduled.

Do not use Tiingo Starter persistent prices, make a paid EODHD
subscription, or redistribute source data. Official terms:
https://app.tiingo.com/tos/ (Nov 5 2026 §1.6);
https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies;
https://live.euronext.com/en/popout-page/getHistoricalPrice/IT0003128367-MTAA
