# R-007 independently inspected outcomes — 2026-11-11

## Audited GitHub evidence (do not substitute CI green for financial validation)

Source PR head at inspection: `fbc165689ab78e65ced486fe4a6a9af39f1dbba5`.
Workflow (PR): https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42891306995
Exact job IDs: `130092850963` (null-world calibration),
`130092850316` (secondary actual-price pilot), `130092851037` (601 tests).

### Preregistered 1,000-world Gaussian null

- All **1,000** synthetic random-walk worlds completed, each with 30 folds, 30
  fake assets, 10,000 same-K random comparisons and 10,000 fold bootstraps.
- False passes of *joint* score diagnostic: **14 / 1,000 = 1.4%**.
- Wilson 95% upper bound: **2.3362%**, below frozen 5% null-gate limit.
- **CRITICAL cost asymmetry:** 996/1,000 worlds have a nominally positive
  lower 95% bound on TOP2 excess vs the N=30 equiponderated universe.
  Mean null excess vs N-leg benchmark was **+3.801507 percentage points**.
  The N-leg benchmark bears many minimum-fee charges on tiny tickets. This
  proves excess-vs-N-leg, in isolation, is **not** a credible alpha statistic.
- 30/1,000 null worlds had spuriously positive IC lower bound.
- A combined 1.4% false acceptance rate does **not** establish predictive
  validity for market data or other return-generating processes.

The frozen V2 protocol and scoring weights were NOT modified to conceal this
limitation. The code now also returns an explicit **cost-matched same-K random
mean/excess**, separate from the original N-leg comparison, as an additional
descriptive diagnostic. A prospective successor protocol should formalize
its choice of primary comparator before outcome observations.

### Real prices / independently inspected secondary pilot

The actual source used was the Aethereal research-and-education CSV, frozen
by SHA-256 `ae7aeba441dc4071bcdc79948b17d49d89e4c5960798d5e6ddc8bf0c4eded0f1`.
Reference used current S&P500 constituents and original ECB reference USD/EUR
FX. Original stock prices were not committed or included in workflow artifacts.
Aethereal license is for research/education only, not commercial redistribution:
https://dataset.aethereal.top/datasets/sp500-stock-prices

Observed:
- 40 retrospectively selected stocks from 397 presently eligible reference
  symbols; 118,606 selected-source price rows.
- 37 preregistered anchor dates; only **4 complete nonoverlapping folds**.
- 28 missing training/FX folds; 5 incomplete future folds.
- Mean TOP2 net proxy: **-0.00006476** (-0.006476%).
- N-leg universe net proxy: **-0.05032371** (-5.032371%).
- Apparent excess vs N-leg: **+0.05025895**, **not alpha evidence**.
- Rank IC: **-0.29871181**; rank vs cost-matched same-K random: **47.44th percentile**.
- TOP2 minus BOTTOM2: **-0.02801008**.
- Excess 95% interval: **[-0.0148853, 0.11540321]**;
  IC 95% interval: **[-0.6673546, 0.14121206]**.
- No corporate action/ISIN reconciliation and SEVERE hindsight/current-member
  survivorship. Live market prices cannot enter the authorized
  FWB/Euronext original-ISIN V2 pipeline on this evidence.

### Research acceptance

**Not accepted** as a predictive or investable outcome. At a minimum,
30 independent, complete, licensed historical folds across 20 eligible
PIT instruments per fold; trading identity/ISIN and corporate action
reconciliation; source rights; and a prospective paper ledger are needed.
Current FX and close-to-close benchmarks are not executable orders.
Issuer tax handling and historical broker statements belong only to
private A. No automatic recommendations, margin/risk approval, or trading.

### Independent reviewer reproduction checklist

1. Inspect exact GitHub Actions **job logs**, including counts and seeds,
   not just README or green check.
2. Verify every 2020–2026 fold pre-trade information cutoff and test why
   only 4 actual-source windows survive.
3. Reconcile same-K net comparison vs minimum-fee N-leg bias,
   independently check 1,000 null-world false passes.
4. Verify vendor original SHA, historical point-in-time universe,
   delistings, splits, dividends, adjusted close and FX release days.
5. Separate hindsight retrospective evidence from out-of-sample
   prospective paper trading and original licensed executable input.
6. Reconcile any eventual per-ISIN tax treatment with documented broker
   evidence inside private A.

Evidence as-of 2026-11-11; record is a reproducible diagnostic, not a
new protocol preregistration.
