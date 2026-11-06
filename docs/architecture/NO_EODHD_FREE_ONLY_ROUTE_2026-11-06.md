# V3.0.0 — source route without EODHD or paid subscriptions

Effective 2026-11-06. This is an execution policy, NOT a new architecture or an investment conclusion.

## Provider decision

**EODHD is excluded.** Standard CLI EODHD price/catalog/crosswalk actions fail with EODHD_DISABLED_NO_SUBSCRIPTION, EODHD input is rejected by the standard bundle-build command, and its live CI smoke is disabled. Historical modules remain in the codebase for test compatibility only. No EODHD sign-up, account, API key or payment is required.

Permitted paths:
- **Tiingo Starter ($0/month):** opt-in personal/internal US stock/ETF histories. Account token only in local TIINGO_API_TOKEN; no paid tier. Official terms: https://www.tiingo.com/pricing and https://www.tiingo.com/documentation/ .
- **ECB:** official EUR/USD historical fixing XML or CSV with timestamp, SHA-256 and same-day alignment. No API key. https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/
- **SEC:** official annual corporate accounts, issuer coverage and SEC CIK-linked tickers. No subscription; obey rate limits and contact identity. https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- **Deutsche Boerse Xetra:** official reference catalog for security identity/type, NOT free market-price history or broker execution.
- **Alpha Vantage:** existing free raw DAILY pilot only; TIME_SERIES_DAILY_ADJUSTED is premium and must NOT be used as a free-data assumption. https://www.alphavantage.co/documentation/
- **Approved local quote snapshots:** original authorized raw files plus explicit rights/source timestamp/ISIN/venue/hash and corporate-action review. Never scrape around anti-bot/captcha or claim free Yahoo historical CSV downloads if a subscription is needed.

## Actual free US price-to-screen contract

1. Opt in to Tiingo Starter on the individual's own free account, subject to personal-use terms. Never copy the token to issues, public CI or prompts.
2. Run the already-implemented local Tiingo single-symbol intake under data/private, requiring independently checked ISIN/ticker/venue and rights acknowledgment.
3. Obtain the official ECB EUR/USD source via existing explicit offline collector; keep the original raw bytes and generated metadata privately.
4. **New:** run 'investresearch-b bind-ecb-fx --spec PRIVATE_TIINGO_SOURCE/BUNDLE_INPUT_SPEC.json --ecb-meta PRIVATE_ECB_METADATA.json --output PRIVATE_NEW_BOUND_SOURCE.json'. This verifies official ECB URL, original SHA-256, UTC collection timestamp, as-of cutoff and presence of dated FX observations; it does not make up absent rates.
5. Run 'investresearch-b build --spec PRIVATE_NEW_BOUND_SOURCE.json --output PRIVATE_NEW_BUNDLE', followed by existing 'screen', 'tactical', 'risk', then the private A integration runner. Scores remain historical research-only, not executable prices or ISIN-specific tax decisions.

The actual B source→B risk path has been tested end-to-end with **synthetic test prices and FX via the EXTERNAL code path** (not live quotes). The B CI source tests additionally check malformed FX, missing evidence, conflicting metadata and EODHD disabled-before-network. Verified test run: https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42192677312 (410 tests passed, EODHD job skipped).

## Zero-cost European exchange transparency (not 61-session backfill)

Official EU venue data can help the **permanent** engine without a paid provider: Euronext delayed MiFID II data (https://www.euronext.com/en/data/pricing-specs-agreements/mifid-ii-compliant-data) is free and held for at least 24h, while Deutsche Börse delayed pre/posttrade Xetra files (https://www.mds.deutsche-boerse.com/mds-en/real-time-data/Delayed-data) are freely available with a 15-minute delay and retained until the next business day. Euronext use/distribution terms (https://marketdata.euronext.com/data-reporting-service/trades-file) still apply, and neither venue's delayed snapshots is an independent split-adjusted 61-session OHLCV historical feed. Future intake must reconcile venue/MIC, original trade flags, instrument mapping, corporate actions, missing sessions and usage rights in private storage. No automatic scraping or paid feed fallback has been activated.

## Completed executable source pipeline — 6 November 2026

A reproducible no-EODHD full-stack path is now available:

- Free Tiingo personal intake for one ISIN: `tiingo-personal-collect`.
- **NEW:** explicitly reviewed personal batch intake of 2–20 symbols per invocation, `tiingo-personal-batch`. This is deliberately below Tiingo Starter's currently advertised 50 requests/hour limit. Every instrument needs a valid ISIN, venue (XNAS/XNYS), actual sector and ethical oil exposure review, and **two independently selected HTTPS reference URLs**. The URLs are evidence pointers, **not a software fact-check or broker certification**. Account key only from `TIINGO_API_TOKEN` in a private local environment; no public CI provider calls. No hidden retries, paid endpoint, polling or automatic token charges.
- **NEW:** `merge-free-tiingo --source-spec PATH1 --source-spec PATH2 [repeat] --output data/private/MERGED.json` combines 2–500 separately acquired, same-as-of Tiingo source specs with independent source-file SHA-256, ISIN, provider and identity uniqueness. A free account alone does **not** guarantee valid ISIN mapping. It rejects EODHD or unknown feeds.
- Bind the ONE official ECB fixing history once with `bind-ecb-fx --spec data/private/MERGED.json --ecb-meta PRIVATE_ECB_META.json --output data/private/WITH_ECB.json`, then `build --spec data/private/WITH_ECB.json --output data/private/NEW_BUNDLE`.
- Existing Blocco B `screen`, `tactical`, `risk` and private Blocco A `run_integrated_decision2026.py` work on the resulting original-source bundle and produce research, tax-review, risk and dashboard. They do not provide executable prices, verified fiscal treatment or buy recommendations.

**Material evidence:** B full-source contract and negative tests 434 PASS, [CI 42199597932](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42199597932). The A→B entire code path (including private fiscal review) has been executed on **2 fictional USD instruments with fictional official-format ECB fixing** and prominently displays a fictional-data watermark. Never present its rankings as market evidence.

**Operator-only batch manifest example (not authenticated, no real instruments):**
```json
{
  "schema_version": "r004-tiingo-free-bounded-batch-v1",
  "instruments": [
    {
      "isin": "<independently checked valid ISIN>",
      "symbol": "<verified Tiingo symbol>",
      "venue": "XNAS",
      "instrument_name": "<official issuer/security name>",
      "asset_type": "EQUITY",
      "sector": "<reviewed issuer sector>",
      "oil_exposure": "none",
      "reference_urls": ["https://<first official source>", "https://<second independent official source>"]
    }
  ]
}
```
Add **2–20 genuinely verified instruments** before invoking the command, not the single placeholder shown. Keep the manifest under `data/private/`. Run:
```bash
investresearch-b tiingo-personal-batch --reviewed-manifest data/private/REVIEWED.json --acknowledge-personal-terms --identity-reviewed --output data/private/TIINGO_BATCH_NEW
```
On a failed partially completed batch, previous private evidence is kept, but no automatic retry is made. Account requests may already have been consumed; select remaining symbols for a new batch, then use `merge-free-tiingo` on completed intake specs. Tiingo terms are personal/internal and expressly prohibit redistribution; the user's own agreement controls their usage.

## Pending V3 acceptance gates

M3: permitted genuine 61-session adjusted historical data and independent split/event checks across representative assets, including EU. M4: real global 200+ scored funnel, valuation, factor/catalyst research; no substitution with unranked listings. M5: independent factual verification of AI citations and free-tier account proof. M2/M6: fiscal and broker evidence for personal 2026 decisions, real-source dashboard validation. R-013 remains no automated orders. Leave PRs unmerged until review.
