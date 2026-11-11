# First real-source 1/3/6-month exploratory price replay — 11 Nov 2026

**Observed result, not model validation.** A real market-price educational
research experiment was executed by GitHub Actions using the original
score functions and the previously registered 1/3/6-calendar-month
framework. There were no payments, orders, new stock recommendations,
raw original price artifacts or tax-wallet access.

## Execution and frozen provenance

- Full source-based execution:
  https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/43064389030
  job `secondary_real_1_3_6m_educational_pilot`, conclusion **success**.
- Secondary source experiment protocol was committed BEFORE this job:
  `config/backtest/secondary_aethereal_real_1_3_6m_pilot_2026-11-11.json`
  commit `22d623e42d463cd7b52239f13b08e3330122a65d`.
- Secondary experiment protocol SHA-256
  `0506e74aef770a2a90109cc6a390552ef00d0f01ed0ddf0cbdbe4390466c50ec`.
- Core 1/3/6-month as-of backtest protocol SHA-256
  `e4c6a4ed77031bf0b02c4ce1f07d418219e8b17ace3bedbca2d7585a7adef268`.
- Original Aethereal prices (updated source vintage, run-local SHA-256)
  `6480d9c288ae7521a6a44dbb75786cbec3a62149bcfaecc263999290fa30d020`.
- Original current S&P 500 company reference SHA-256:
  `853f2fe3c4b126b6b251dbc7c81510de22c17167f2c0e646212e38e1cc45420f`.
- Original official ECB reference exchange-rate XML SHA-256:
  `e00ae31dccd722aa1edb5970252f82641c70a0c873e3a0556554259336043af1`.
- Maximum source date 2026-11-09. The price dataset is rebuilt daily;
  subsequent versions MUST NOT be silently treated as this vintage.
- Source: https://dataset.aethereal.top/datasets/sp500-stock-prices
  (research and education licence); roster:
  https://dataset.aethereal.top/datasets/sp500-companies (CC0);
  ECB EUR/USD original reference fixes.
- 40 instrument identities chosen by the PREVIOUSLY committed hash-seed
  original current-index cohort policy; energy and oil-focused industries
  excluded by the as-of schema. Selection is NOT proven to exclude every
  indirect issuer oil exposure.
- Selected original security-price observations: 118,646.
  Prior-or-equal ECB FX fix mapping used on 1,075 market observations;
  latest preceding ECB fix lag was 4 calendar days, no missing-fix rows.
  ECB FX references are NOT executable broker buy/sell rates.
- Only aggregate statistics and source hashes went into the public CI log;
  individual security prices, names, picks and per-position performances
  were not saved, committed, uploaded or printed.

## Observed educational results (returns as fractional net of simulated fees)

| Metric | 1 calendar month | 3 calendar months | 6 calendar months |
| --- | ---: | ---: | ---: |
| Complete nonoverlapping matured folds | 24 | 5 | 1 |
| Matured unresolved folds (not dropped from acceptance) | 13 | 14 | 9 |
| Other ex-ante overlapping anchors | 0 | 18 | 27 |
| Average selected TOP2 return | -0.02270106 | -0.01033163 | -0.12321703 |
| Mean matched-K random benchmark | -0.00499279 | -0.00624690 | -0.05943985 |
| Mean TOP2 minus matched-K | **-0.01770827** | -0.00408473 | -0.06377717 |
| Net P&L per hypothetical EUR 10,000 | -227.01 | -103.32 | -1232.17 |
| Bootstrap 95% paired excess CI | [-0.02960869, -0.00368879] | [-0.05571285, 0.04591194] | N/A |
| Percentile vs 10,000 same-K random portfolios | 0.0198 | 0.4448 | 0.3146 |
| 30 independent folds + complete-data gate | **FAIL** | **FAIL** | **FAIL** |

**Interpretation:**
- On the 24 *complete* one-month windows, the original B score lagged
  the two-stock random benchmark by 1.77 percentage points on average;
  the estimated paired excess confidence band on those selected windows
  is entirely negative.
- **This does NOT prove a negative true alpha:** 13 other monthly
  matured windows have unresolved source outcomes or potential >15%
  price changes and are excluded from return averaging, while the
  statistical completeness gate correctly remains FALSE.
- Three months has only five complete folds and six months only one;
  the resulting point estimates cannot establish superiority or
  inferiority. Multiple horizons reuse correlated selections.
- No positive or negative predictive performance has been **certified**.
  In particular, DO NOT optimize/change the ranking weights using this
  result and then retest on the same 2021–2026 observations.

## Limits that prevent financial decisions

1. **Severe survivorship/hindsight bias:** source covers 2026 **current**
   members of the S&P 500 and excludes companies delisted/removed earlier.
   Its 2026 membership identities cannot be authenticated for 2021–2025
   despite using a seed chosen before consulting this fresh run's returns.
2. **US stocks only:** not the intended European multi-asset investable
   universe; no authenticated ISIN/MIC, certificates, ETF/ETC/ETN, issuer
   fiscal category or bank settlement.
3. **Historical adjustment vintage:** issuer dividends/splits/delisting
   cashflows are source-adjusted estimates, not independently reconciled
   contemporaneous as-of data; large legitimate crashes remain potentially
   censored by the conservative >15% daily jump rule.
4. **Commission/FX are assumptions:** EUR 10k, K=2, 0.19% each-side, EUR 7
   minimum, 0.25% each-side USD conversion friction, ECB observed prior or
   same-day reference fix. No independent executable market or bank proof.
5. **Source use licence:** Aethereal marks prices free for research and
   education; it is NOT a commercial execution-data licence. Original CSVs
   were downloaded into GitHub job memory only, not distributed.
6. **No ex-ante unseen holdout:** the experiment follows prior historical
   pilot reviews and uses a price file downloaded in 2026; source timestamp
   hash is recorded, but not a 2021 archival snapshot.
7. **No full private A license/PIT certification on original market data:**
   A's independently tested 1/3/6-month contract remains validated
   end-to-end on FICTIONAL bundles only, not authenticated historical
   issuer records for this secondary source. This educational pilot uses
   B's same core time-travel scorer and matched-cost evaluator directly.

**Outcome:** REAL historical-price exploratory TEST EXECUTED, results are
mostly non-positive/inconclusive, and genuine PIT predictive/financial
validation remains BLOCKED by external evidence. No `trade_ready`,
no brokerage action, no claims of minusvalenza compensation.
