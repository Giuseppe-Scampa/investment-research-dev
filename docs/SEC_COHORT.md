# SEC EDGAR — expanded annual research cohort (M3, informational)

The existing **4-company live pilot** has been expanded to a **bounded, opt-in
cohort of up to 24 requested tickers**. `config/sec_cohort_example.json` contains
18 explicit symbols. This is an *engineering coverage sample*, not an investment
ranking, sector-representative sample, recommendation or complete universe.

## Running it

The secret `SEC_RESEARCH_CONTACT` is an email address used **only in the HTTP
User-Agent**. It belongs in the local process environment or in a GitHub Actions
repository secret, never in code, input JSON, logs or downloadable artefacts.

```bash
python -m pip install -e .
# Explicitly authorized SEC access, at most one catalog + 24 issuer requests:
investresearch-b sec-pilot --live-confirm \
  --cohort config/sec_cohort_example.json \
  --output reports/generated/block_b/sec_cohort
# Or select 1–24 symbols:
investresearch-b sec-pilot --live-confirm --symbols AAPL,MSFT,NVDA,AMZN
```

The first command requires `SEC_RESEARCH_CONTACT` in the environment or
`--sec-contact` on a **trusted local machine**. Do not pass a contact address
as a GitHub Actions CLI argument. `--live-confirm` is mandatory. The catalog is
current, so live acquisition requires `--as-of` equal to today. This is **not**
a survivorship-bias-free backtest for historic dates. Network errors (403/429,
timeouts, etc.) stop the run: no silent retries or paid fallback. Unique CIKs
are fetched at most once, and requests are spaced at least 1.2 seconds apart.

## Evidence and checks

The SEC source files are cached locally with SHA-256 and provider metadata.
Before report generation, the parser checks the matching issuer CIK, source
host and path, retrieval timestamp, file hash, period, annual report form and
`filed` cutoff. It prefers revenue and income from **one accession**, preventing
a mixture of incompatible annual filings.

In addition to the latest annual revenue, net income and net margin, the new
module optionally reports *year-on-year revenue growth* and *net margin change*
when the previous fiscal year is represented in the **same SEC accession and
same XBRL concepts**. This is intentionally stricter than taking two arbitrary
companyfacts observations. When the comparable previous year is absent or
contradictory, the comparison stays blank and receives an explanatory status.
Negative historical income does not produce a misleading income growth rate.

A filing whose year-end is more than **550 days before the reference date** is
flagged stale rather than counted as usable annual coverage. The 550-day
threshold is a research policy, not a SEC deadline or a legal rule.

### Outputs

- `SEC_ANNUAL_RESEARCH.json`: provenance-aware derived results and explicit gaps.
- `SEC_ANNUAL_RESEARCH.csv`: one row per selected ticker; includes comparison
  status and source accession.
- `SEC_ANNUAL_RESEARCH.md`: readable coverage table.

Only *publicly available derived SEC values and source hashes* may be exported.
Raw issuer JSON and the contact secret remain in an ignored local cache and
must **not** be committed to the public repository. Source hashes establish
cache integrity, not an SEC signature or valuation certificate.

## Limitations and next gate

- SEC companyfacts report US-GAAP XBRL and may not cover certain foreign issuers,
  financial companies or nonstandard revenue tags. Such companies remain
  `REVIEW_SEC_ANNUAL_FACTS_UNAVAILABLE`.
- Fiscal year-ends and accounting policies differ across issuers; the margin
  and revenue growth figures are not comparable investment rankings.
- The SEC ticker association is a **current** file, not a verified historical
  component universe. It does not supply ISIN, sector, ethical exposure or
  exchange-executable market prices.
- **M4 live investment ranking remains blocked** until market data are legally
  usable for the intended purpose, adjusted for corporate actions and checked
  against verified tickers/exchanges and actual liquidity.

**Primary references:** [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[SEC Accessing EDGAR Data / fair access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
