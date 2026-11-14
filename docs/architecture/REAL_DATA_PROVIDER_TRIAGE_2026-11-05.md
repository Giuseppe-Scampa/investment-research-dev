# Market-data acquisition: factual free-tier comparison — 2026-11-05

**Purpose:** obtain a sufficiently broad, lawful, split-adjusted historical
daily feed for Decision 2026 before upgrading R-006/007 from PARTIAL.

## Comparison based on official provider websites

| Source | Verified public offering | Key limitation for this engine | Immediate action |
|---|---|---|---|
| SEC EDGAR | Current US company list and issuer historical filings; no account | Not EOD quotations, ISIN/venue, ETF/ETN/cert price feed | Continue as identity and fundamentals source; keep SEC contact User-Agent |
| ECB | EUR reference FX public APIs | Fixing time is not synchronized with US equity close | Retain as tagged non-synchronous FX reference |
| Alpha Vantage Free | 25 requests/day; TIME_SERIES_DAILY/compact 100 **raw** bars; FSLR live proven on 2026-11-04 | DAILY_ADJUSTED is Premium; 25/day is limiting for 200+ instruments, no non-display rights certificate | Use only focused validation, not entire universe |
| Twelve Data **Basic** | Official pricing: 8 API credits/minute, 800/day; 3 markets, US stocks/ETFs; internal non-display usage indicated; time_series supports `adjust=all/splits/dividends/none` | Basic does **not** claim EOD Europe multi-market or whole multi-asset coverage; exchange/ISIN availability and cache/use rights must be checked, adjusted result validated on live sample | **First next-source candidate**; request a free Basic account only before explicit single-symbol pilot, no billing |
| Financial Modeling Prep **Basic** | Official pricing: 250 API calls/day and limited historical data; EOD full API documented | Personal license terms restrict downloading/copying without prior written authorization and display/redistribution; unclear suitability for storing source history in engine | **Do not ingest** until license use confirmed in writing; do not assume 250/day means permission |
| Euronext NextHistory | Official EOD price, volume, corporate actions, splits, dividends, MIC; subscription/datashop | Commercial data/rights may be required, particularly for non-display | Escalate for EU and ETPs if public sources fail |

### Official documentation checked

- SEC: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Alpha Vantage: https://www.alphavantage.co/documentation/
- Twelve Data pricing: https://twelvedata.com/pricing
- Twelve Data time_series: https://twelvedata.com/docs
- Twelve Data personal terms: https://twelvedata.com/terms
- Twelve Data adjusted prices: https://support.twelvedata.com/en/articles/5179064-are-the-prices-adjusted
- FMP pricing: https://site.financialmodelingprep.com/pricing-plans
- FMP TOS restrictions: https://site.financialmodelingprep.com/terms-of-service
- Euronext NextHistory: https://www.euronext.com/en/products-services/nexthistory

## Decision gate

1. Keep user funds / broker information exclusively in private Block A.
2. For Twelve Data use only personal noncommercial testing and **verify the
   actual Basic entitlements** (no automatic paid upgrade). First test
   AAPL/FSLR and, if allowed, an ETF. Explicitly inspect `meta.mic_code`,
   symbol, type, currency, bar adjustment mode and continuous 61 sessions.
3. Confirm source licensing, adjustment semantics, date staleness, volume
   integrity, instrument identity/ISIN and corporate-action coverage **before
   promoting any samples to the R-008 ranking**.
4. Investigate official EU venue sources and certificate issuers separately;
   there is no evidence Twelve Basic alone solves European ETC/ETN/cert data.
5. Only then run `investresearch-b tactical` from the real local bundle and
   import paired JSON into private `investresearch tactical-c`.

**No account is created by writing this analysis; no financial operation,
future return forecast, license authentication or paid subscription occurs.**
