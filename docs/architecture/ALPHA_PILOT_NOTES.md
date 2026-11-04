# Alpha Vantage FREE daily — R-004/R-005 local diagnostic

Implementation: `src/investresearch/research_alpha_pilot.py`, one opt-in
`investresearch-b alpha-pilot` request, no retry, no cron, no bulk download.

Expected official payload: `Meta Data` + `Time Series (Daily)`, keyed by ISO
session date with fields `1. open`, `2. high`, `3. low`, `4. close`,
`5. volume`. Errors and API notes fail closed. The key is injected only from
`ALPHAVANTAGE_API_KEY`; never persisted, printed or included in a commit.

Prices are **raw, not adjusted** and the free compact endpoint has up to 100
bars. The data lacks issuer ISIN and authenticated exchange MIC. Therefore
`ALPHA_DAILY_UNVERIFIED.csv` remains an **unranked local diagnostic**, not an
input promoted to `UNVERIFIED_NOT_TRADE_READY` general screening. This avoids
mistaking provider availability for legal entitlement or corrected returns.

All unit tests are strictly synthetic/offline. No real account is needed
until a deliberate authorized pilot; no paid subscription is needed for tests.

See [Account and source readiness](ACCOUNT_AND_SOURCE_READINESS_2026.md)
and the primary source:
[Alpha Vantage documentation](https://www.alphavantage.co/documentation/).
