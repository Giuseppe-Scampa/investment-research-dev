# R-004/R-005 — Original Euronext Milan / Paris history integration

**Status 7 November 2026:** offline code path implemented; source authenticity,
licensing and live European 61-session input still require external proof.

Official reference: Euronext historical-download popout
`https://live.euronext.com/en/popout-page/getHistoricalPrice/{ISIN}-{MARKET}`.
The page provides CSV, decimal-separator and date formatting options and
Adjusted / Non-Adjusted selection. The software **does not automate** this
download, scrape pages, call undocumented endpoints or buy NextHistory.

The separate Euronext NextHistory service offers paid/commercial datasets,
including Borsa Italiana EOD, adjustment factors and corporate actions.
Euronext says delayed *display* is free for certain internal uses, but
non-display use of market data can involve distinct licensing conditions.
A free visible quote or download option is **not** licence approval for bulk
algorithmic modelling or resale. The user must check actual original-source
terms for any intended internal automated use.

## Markets implemented (real market codes → existing B calendars)

| Original Euronext code | B screening venue | Local scope |
| --- | --- | --- |
| MTAA | XMIL | Euronext Milan regulated equities |
| ETFP | XMIL | ETFplus ETFs/ETPs, legal classification separate |
| EXGM | XMIL | Euronext Growth Milan |
| ETLX | XMIL | EuroTLX; only EUR unit-price securities, no par-based bonds |
| XPAR | XPAR | Euronext Paris |

Other market codes and calendars, including Amsterdam, Brussels, Dublin
and unusual product units, are **not automatically inferred** or ranked
from Italy/France calendars. Source-market code and exchange calendar
identity are distinct fields and must never be conflated.

## Operator workflow

1. Navigate to the **specific original instrument** Euronext page and
   open its Historical data download. Choose the original instrument's
   valid ISIN and market segment; ensure the source is quoted in EUR.
2. Choose CSV, not an Excel workbook. Choose date/numeric locale explicitly,
   disable base-100 values and **record** whether the Euronext UI exported
   Adjusted or Non-Adjusted prices. Preserve original file bytes.
3. Record exact CSV column names for date, EUR close and **quantity traded**
   (volume). Do not substitute EUR turnover for volume. Use exact source URL,
   UTC retrieval date and SHA-256. Consent to the applicable personal/local
   rights only after independent operator review. Do not claim the code
   independently verified terms or issuer identity.
4. Copy `config/euronext_milan_history_manual_example.json` privately;
   set `as_of` no later than acquisition, instrument ID/ISIN/class/sector,
   and select the actual CSV date and numeric settings.
5. Select `adjustments_claimed` independently for each of **splits,
   dividends and subscription rights**. If some corrections are unknown or
   export is non-adjusted, the series can enter a **coverage report** but
   receives **no market rank**. Even a fully ticked Adjusted export is
   marked *not independently corporate-action-verified*.
6. Store original CSV and the one-security JSON exclusively in
   private `data/private` (or an external local path), then run the
   combined original source workflow:

```sh
PYTHONPATH=src python tools/run_mixed_source_decision2026.py \
  --block-b-root ../investment-research-dev \
  --source-spec data/private/euronext/ENEL_ORIGINAL_SPEC.json \
  --source-spec data/private/fwb/XETRA_ORIGINAL_SPEC.json \
  --source-spec data/private/usa/TIINGO_ORIGINAL_SPEC.json \
  --ecb-meta data/private/ecb/ECB_META.json \
  --output data/private/new_three_market_run
```

The command is in the **private A** repo. For EUR-only research, omit
`--ecb-meta`. Original Euronext files remain local; the B source builder
renormalizes them into its checked dataset and computes only historic EUR
metrics. B→A outputs are a non-executable research diagnostic, not
executable quote, forecast, portfolio advice or fiscal certification.

## Acceptance

- Original official Euronext CSV actually obtained for its instrument,
  legally permitted for the intended analytic use and reconciled to the
  issuer/market source as of a particular date.
- At least 61 consecutive verified trading sessions for price scoring;
  adjusted vs raw split/dividend rights reconciled separately.
- Representative Europe+US 200+ real instrument pipeline and independent
  A risk/fiscal review must be proved before full M3/M4 DONE.
- Local two-venue Euronext parser and B→A test fixture only demonstrate
  software correctness; all figures in those tests are **fictional**.

Official documentation:
- https://live.euronext.com/en/popout-page/getHistoricalPrice/IT0003128367-MTAA
- https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies
- https://www.euronext.com/en/products-services/nexthistory
