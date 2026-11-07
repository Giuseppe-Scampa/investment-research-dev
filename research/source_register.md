# Public source references (historical and illustrative)

The project is not a source of live or executable market quotes. Individual data points need source validation and effective dates.

- [Borsa Italiana market data](https://www.borsaitaliana.it/)
- [European Central Bank](https://www.ecb.europa.eu/)
- [Eurostat](https://ec.europa.eu/eurostat)
- [SEC EDGAR filings](https://www.sec.gov/edgar/search/)
- [Italian tax administration](https://www.agenziaentrate.gov.it/portale/)
- [Normattiva](https://www.normattiva.it/)

See `docs/FISCAL_SOURCES.md` for tax-law references and open questions. No personal banking documents are included.

## Provider readiness (verified 4 November 2026)

- [SEC official EDGAR access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data):
  public free source; identified User-Agent, fair-access policy.
- [Alpha Vantage TIME_SERIES_DAILY](https://www.alphavantage.co/documentation/):
  raw/unadjusted recent 100 compact bars on the documented free endpoint;
  API key required only for the optional local pilot; adjusted DAILY is premium.
- [Alpha Vantage free-account request limits](https://www.alphavantage.co/support/):
  25 calls per day on the general free program as publicly documented.
- [Euronext NextHistory](https://www.euronext.com/en/products-services/nexthistory):
  exchange source for EOD, adjustment factors and corporate actions; access
  is distinct from freely viewed delayed quotes and must be licensed as needed.
- [Euronext internal/non-display use policies](https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies):
  do not infer automated computation rights from public display availability.

All providers are research sources, not unconditional rights to copy, use
for non-display derived calculations, publish datasets or automate trading.
See [readiness plan](../docs/architecture/ACCOUNT_AND_SOURCE_READINESS_2026.md).
