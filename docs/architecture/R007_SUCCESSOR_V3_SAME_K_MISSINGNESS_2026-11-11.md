# R-007 — Registered V3 successor: SAME-K primary, no future-missingness selection

Date: 2026-11-11. Scope: **new historical experiment only**, not changes to
V3.0.0 architecture or to V1/V2 frozen outcome protocols.

## Pre-registration / chronology

The byte-for-byte V3 successor protocol was committed **before** the evaluator
and its first experimental tests:

- Protocol-only registration commit:
  `f60211c1130790460b4b1402719354a507549353`.
- File: `config/backtest/v3_long_horizon_protocol_v3_2026-11-11.json`.
- Git blob SHA-1: `2f48675b0b0d319becf360854317d05a708affb7`.
- Content SHA-256:
  `4cab005308d04968f3a2d611e1cdfa3bebc154a8b60ae690761113b0edb0f0f4`.
- V1 and V2 protocol bytes, validators, their evidence and source vintages
  remain unmodified. V2's prior +3.80 percentage-point null fee artefact
  motivated this V3, so **previously inspected V2 source data are not an
  independent confirmatory holdout for V3**, even if re-ingested later.

The V3 frozen score weights are unchanged. There is NO hidden adaptation,
re-ranking on the holdout or algorithmic return forecast in this change.

## Mathematical correction

Let `N` be the frozen pre-outcome eligible universe and `K=2`. All
hypothetical legs are sized using `EUR 10,000/K`, 0.19% each-side
commission and EUR 7 each-side minimum. USD hypothetical FX friction remains
0.25% per side.

For fold `t`, define `net_i(K)` from each universe member's own entry
and exit observations, but charged exactly **K-leg costs**. Then:

- `net_TOP2(t)` = mean of two selected members' K-leg net returns
- `E[net_random_K(t)]` = mean of `net_i(K)` across **all N as-of members**
- **Primary** `excess_same_K(t) = net_TOP2(t) - E[net_random_K(t)]`

The expectation identity is exact for uniform K-of-N sampling: it introduces
no Monte Carlo noise. The **separate** 10,000 randomized 2-position
portfolios remain a percentile/ranking control. The historical N-leg universe
comparator, which charges N minimum commissions, remains a **descriptive
secondary statistic** and is explicitly prohibited as evidence of alpha.

Statistical uncertainty is from 10,000 complete **fold-level** paired
bootstrap resamples, frozen seed 20261117. The unchanged Spearman rank IC,
random-portfolio >=90th percentile, TOP2 > BOTTOM2, >=30 independent folds,
>=20 members per fold, null control and external review are not waived.

## Ex-ante treatment of missing futures

**Before looking at any future observation** at a decision time, V3 fixes:
all eligible IDs in ranking order, their SHA-256, TOP2/BOTTOM2 IDs and the
calendar-determined planned exit date of the *entire* as-of cohort. Planned
non-overlap reserves the full future window **even when that later outcome
proves incomplete**; other decision anchors cannot be substituted ad hoc.

Each anchor is reported in `ex_ante_anchor_audit`:

1. source cutoff not reached, or ex-ante overlapping anchor;
2. inadequate as-of historical eligible cohort (decidable at T);
3. future 30-interval observation **not yet matured** by source cutoff;
4. matured complete cohort;
5. matured cohort with **any unresolved future among original as-of members**.

Type 5 contributes to `matured_outcome_unresolved_anchors` and records all
missing IDs. It is **never** rewritten as fewer eligible members, zero return,
last available price, a new winner, or an implicitly successful fold. Some
complete folds can still be shown as explicitly **censored exploratory
diagnostics**, but **ONE unresolved matured cohort forces the complete-data
statistical gate to FALSE**, even if all remaining complete folds look strong.

Exchange delistings, unpaid terminal distributions, suspensions, adjusted
corporate actions, provider outages and FX problems need original point-in-time
evidence to determine actual realized cash flows. V3 intentionally does not
fabricate a terminal delisting value or classify data loss as a -100% return:
these cases remain unresolved and block validation.

This gate prevents false positive inference from selecting only fully observed
profitable windows; it does **not** solve universe survivorship bias if the
input omitted past delisted instruments before constructing the as-of cohort.

## V3 1,000-world synthetic null calibration

Full success run:
https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/43016039580

- 1,000 independent Gaussian no-alpha worlds; 30 independent folds of 30
  FICTIONAL assets per world, 10,000 K=2 portfolios, 10,000 bootstraps.
- Mean false excess for K=2 selection versus N=30 differently costed
  benchmark: **+0.03835135** (+3.835135 percentage points).
- **Mean false excess versus correct exact same-K comparator: +0.00010892**
  (+0.010892 percentage points, numerically close to zero).
- Full joint-gate false passes: **4/1000** (observed 0.4%; Wilson 95% upper
  1.024%, within preregistered 5% limit).
- All returns here are synthetic. Gaussian zero-alpha walks do not model
  real tail risk, delistings, macro regimes, source permissions, pooled
  dependence, data snooping or actual future profitability.

B unit tests also verify the frozen protocol hash, exact arithmetic, positive
returns unaffected by future-score leakage, a removed future session
triggering a matured-unresolved rejection and immature windows staying
PENDING. V3 check: **608 pytest PASS** as of 11 Nov. A independently
recomputes the results, but no human auditor has signed off on private A.

## Offline entrypoints

The bundle must already exist and contain lawful private original records
with dated source provenance. **DO NOT commit downloaded market data.**

```bash
mkdir -p data/private
investresearch-b historical-validation-v3 \
  --bundle data/private/AUTHORIZED_EXISTING_BUNDLE \
  --output data/private/NEW_V3_RETROSPECTIVE_REPORT.json

investresearch-b null-calibration-v3 \
  --worlds 1000 --output data/private/NEW_V3_NULL_AGGREGATE.json
```

Outputs refuse overwriting. `trade_ready=false` and
`predictive_edge_certified=false` stay enforced on both report types.
The stand-alone null-calibration CI does not magically turn a retrospective
source bundle into a prospectively certified research result. For A integration
use the *private* `--historical-validation-v3` flag.

## Remaining release blockers

- No rights-cleared and independently adjusted 2020–2026 multi-asset
  historical cohort with delisted instruments, issuer mapping, dates,
  FX timing and corporate actions validated by independent sources.
- No >=30 complete PIT-verified, sufficiently powerful prospective windows;
  and no external authenticated timestamp/vendor/archive attestation.
- No independent proof of result robustness across market regimes, realistic
  transaction costs, turnover and time clusters.
- No confirmed by-ISIN offset classification/tax wallet and executable prices
  from the actual Italian bank.
- ADR-0002/0003 governance and public Git historical privacy disposition
  remain subject to explicit human review; these commits do not authorize
  merge or any trading.

**Status:** V3 software functionality and synthetic falsification gate
implemented; FINANCIAL/OPERATIONAL RELEASE BLOCKED.
