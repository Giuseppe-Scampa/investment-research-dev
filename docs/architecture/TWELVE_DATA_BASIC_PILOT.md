# Twelve Data Basic — free adjusted-source diagnostic (not ranking)

**As-of 2026-11-05; R-004/R-005 PARTIAL.**
Implementation: `src/investresearch/research_twelve_pilot.py` and
`investresearch-b twelve-pilot`. Unit tests are **entirely offline**.
No Twelve Data account or API key has been used yet.

## Why this provider?

- [Official Basic pricing](https://twelvedata.com/pricing) states
  8 API credits/minute and 800/day, **3 market entitlements**, and
  "internal non-display" use; Basic includes **US equities and ETFs**.
  The 800 limit is credits, not an unconditional guarantee of 800
  instruments per day.
- [Official time_series](https://twelvedata.com/docs) documents
  `adjust=all|splits|dividends|none`, `outputsize`, venue metadata
  (`mic_code`) and 1-day OHLCV.
- [Official support](https://support.twelvedata.com/en/articles/5179064-are-the-prices-adjusted)
  states daily historical prices are split adjusted, unlike intraday.
- [Terms](https://twelvedata.com/terms) restrict free-tier commercial
  usage, redistribution, excess caching and third-party disclosure.
  A license for raw public exports or a global rank is NOT assumed.

## Safe single-symbol test

Create only a **free Basic** Twelve Data account for this optional pilot
(the software/tests do not need the account). Keep billing disabled.
Set `TWELVE_DATA_API_KEY` in the **local shell environment/secret store**;
do not paste it into the CLI, GitHub source, user-visible chat or logs.

```bash
investresearch-b twelve-pilot \
  --symbol FSLR --venue XNAS \
  --live-confirm --acknowledge-personal-terms \
  --output data/private/twelve-FSLR
```

The code makes ONE HTTPS request to `api.twelvedata.com/time_series`,
requests `interval=1day`, `outputsize=100`, `adjust=splits`
with venue XNAS or XNYS. It rejects unexpected MIC, currency,
symbol, non-ISO session, future/duplicate dates, invalid OHLCV,
provider errors, oversized payloads and repeated outputs. It does not
fall back to a paid plan, multiply calls, or write outside a local
ignored/private path.

The output files are `TWELVE_SPLIT_REQUESTED_UNVERIFIED.csv` and
`TWELVE_PILOT_METADATA.json`. Metadata includes source and checksum
without API key, venue, currency, first/last date, source type,
and flags:

- `actual_adjustment_independently_verified=false`
- `rights_independently_audited=false`
- `research_status=DIAGNOSTIC_ONLY_NOT_RANKABLE_NOT_TRADE_READY`

**The pilot cannot yet be fed directly to `tactical`:** before using
adjusted values for a live selection, independently verify split
history, volume convention, financial calendar, security identity
(ISIN, MIC), currency, source license and permitted local caching.
Basic entitlement for European venues, ETC, ETN and certificates
must NOT be inferred from general provider marketing.

Use SEC filings for US issuer fundamentals and approved local
EU/ESEF issuer reports for fundamentals; individual providers
do not replace the global evidence and license gates.

## GitHub Actions (no local terminal required)

A separate **manual-only** workflow is already installed on `main`
without merging the V3 draft PR:
[Actions — Twelve Data Basic pilot](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/workflows/twelve-data-manual-pilot.yml).

1. If/when creating the **Free Basic** account, add repository secret
   `TWELVE_DATA_API_KEY` under Settings → Secrets and variables → Actions.
   Never paste this key into ChatGPT or source code.
2. Select `Run workflow`, branch **main**, instrument FSLR (or IBM), and
   execute manually. No push event triggers market collection.
3. The job pins reviewed code to commit
   `211d5d3cc039ec97729d89aef165b09a15000b9b`,
   reports **only** symbol, venue, type, session counts, dates and
   SHA256 hashes to Job Summary, and never uploads raw price files.
4. A missing/unsupported free entitlement or secret fails the job;
   it never upgrades a plan or silently switches provider.

**The workflow has been added but NOT dispatched or validated against
the live Twelve Data API; all price/ranking/data-license gates remain open.**
