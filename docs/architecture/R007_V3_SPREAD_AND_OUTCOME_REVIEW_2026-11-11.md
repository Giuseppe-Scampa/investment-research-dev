# R-007 V3 — Frozen spread scenarios and price-discontinuity diagnostics

Date: 11 November 2026. Scope: **additive audit/test hardening only**.
The registered protocol is unchanged (Git blob `2f48675b0b0d319becf360854317d05a708affb7`);
historical V1/V2, V3 scores, candidate cohort, paired-fold bootstrap,
exact same-K primary metric, null calibrator and statistical gates are unchanged.

## DEF-V3-01: spread/slippage actually implemented

The frozen V3 protocol specifies `slippage_spread_eur_bps_scenarios =
[0,10,25,50]`. For an illustrative **per-side** adverse execution `s = bps /
10000`, instead of observing market bid/ask, the source close prices are
stressed symmetrically: buy `P_entry * (1+s)`, sell `P_exit * (1-s)`.
For a leg with initial EUR cash `C`, commission fraction `f`, minimum
commission `m` and FX friction `x` on each side for USD only:

- `buy_fee = max(C*f, m)`
- `spendable = C - buy_fee - C*x`
- `sale_cash = spendable * (P_exit/P_entry) * (1-s)/(1+s)`
- `sell_fee = max(sale_cash*f, m)`
- `net_return = (sale_cash - sell_fee - sale_cash*x)/C - 1`

The same **K=2-leg capital per instrument**, commission minimums, exposure and
FX treatment are applied to every member in the fixed original as-of cohort.
The exact expected random-K net return is the mean of those same-cost member
returns, not the old N-leg portfolio with punitive minimum fees.

`research_slippage_v3.py` implements these *descriptive scenarios only*.
The standard 0-bps run must match V3's unchanged `_net_trade` output to
floating-point tolerance. The report now carries
`folds[].slippage_spread_scenarios_DESCRIPTIVE_ONLY` and
`slippage_spread_scenarios_DESCRIPTIVE_ONLY` at aggregate level, with
`slippage_sensitivity_changes_primary_gate=false`.

**Interpretation:** each input bps is charged per trade side (rather than
mislabeling 50 bps as a verified market bid/ask spread). These values are
hypothetical stresses, not real exchange quotes or execution costs. In
particular, positive same-K excess under a stress is not new alpha evidence,
and no new retrospective optimization is authorized.

## DEF-V3-02: daily move >=15% is NOT proof of a split

Existing frozen V3 `_forward` still fails closed if a post-decision return
has an absolute close-to-close move >=15%: a split *or a real crash* may cause
that observation. The new post-freeze classifier records
`JUMP_GE15_PERCENT_CORPORATE_ACTION_OR_REAL_CRASH_UNRESOLVED`; it never
assigns an invented -100% delisting value, reclassifies a true loss as a
winning return, inserts an imputed last price or removes the historical
as-of member. The original fold remains excluded from numerical results
**but included in the matured-unresolved denominator**, and thus the entire
statistical claim remains blocked until independently documented resolution.

This conservative rule protects against accidental false positive claims,
but with real crisis data it may reduce available windows and create a
censored-only descriptive subset. It is not a method for proving that
actual large market crashes were exchange corporate actions. The next
unseen-data preregistration must explicitly encode a licensed verified
corporate-action/delisting return policy before non-censored validation.

## Suspensions / stale EOD closes

At least five repeated, identical adjusted closes within an otherwise
complete 31-session future window now appear under
`suspected_stale_price_or_suspension_ids_NOT_VERIFIED`. Repeated quotes
alone **cannot prove** an exchange trading halt; they could also reflect
rounded thinly traded prices or a stale vendor endpoint. The indicator is
diagnostic, not a silent new outcome or a retrospective exclusion rule.
The source must supply dated exchange notices and adjustment evidence for
release readiness.

## Multiple exchanges and confidence-interval estimator

The next-day entry and 30 return intervals use the exact individual
exchange calendar (XNYS/XNAS/XMIL/XPAR/XETR), locked version 4.13.1.
The pre-committed fold's planned maturity uses the **latest** venue-specific
exit date, so a market holiday cannot make the combined cohort mature early.
A dedicated synthetic test covers multiple calendars around market holidays.

The historical V3 percentile CI convention sorts 10,000 bootstrap whole-fold
means and uses integer/floor indexing at `alpha/2*(N-1)` and
`(1-alpha/2)*(N-1)`. This convention can differ by a very small amount
from linear-interpolated percentiles. Both B and independent A use the
**same frozen estimator**. Do not retroactively switch methods in V3;
a future protocol can compare estimators out of sample.

## Accepted evidence and blockers

- Source code and test cases are synthetic; no actual PIT or dividends,
  split/merger history, delisting proceeds, venue halts, trader spreads,
  licences, tax classification or human audit has been authenticated.
- All extra diagnostic outputs are source-linked by existing report SHA and
  private B→A contract; no original vendor price series are published.
- V3 remains `predictive_edge_certified=false` and `trade_ready=false`.
- V3 was registered after V2 findings. Existing retrospectives cannot be
  called truly unseen confirmatory trials.
