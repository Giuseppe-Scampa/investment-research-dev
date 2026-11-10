# R-004 real-source preliminary audit — 10 November 2026

## Scope and exact outcome

Read-only, transient inspection of **15 public original CSV files** in
`Pubmarks/datasets`, commit-pinned through their Git blob identifiers,
for calendar year 2024. **3,780 real-source-asserted daily OHLCV rows** were
retrieved (252 rows for each ticker). Every file had the advertised
`date,open,high,low,close,volume` schema, unique 2024 dates, positive close
and nonnegative volume. This is a preliminary **input-format/provenance**
pilot — not authenticated exchange prices, corporate actions, adjusted total
returns, licensed data, issuer ownership, or a market-model backtest.

**Important licence blocker:** the repository currently has no GitHub
SPDX licence declaration; publishing a file does not grant persistence
or redistribution rights. The files have no `adj_close`, split/dividend
events or currency/exchange legal-class proof. Consequently, **none** was
admitted to V1/V2 authenticated input, ranked, used for AI prompts,
committed as raw data, or promoted to a recommendation.

Source: https://github.com/Pubmarks/datasets
File path pattern:
`data/stocks/{SYMBOL}/2024/ohlcv.csv`.

## Actual file evidence (Git blob hashes, never price rows)

| Symbol | Rows | First | Last | Git blob SHA-1 |
|---|---:|---|---|---|
| AAPL | 252 | 2024-01-02 | 2024-12-31 | `1831b51a44484ef8a15c9a2c12c92f76e20fe4a0` |
| ACN | 252 | 2024-01-02 | 2024-12-31 | `7b70ce17685a12284fe9e9878264054c5c51b705` |
| ADBE | 252 | 2024-01-02 | 2024-12-31 | `97735a1cf782b5c6adcd81cc1bc9914e003951bd` |
| CRM | 252 | 2024-01-02 | 2024-12-31 | `993d717994d4c474e724e9c1b7b492ce75c02322` |
| GOOG | 252 | 2024-01-02 | 2024-12-31 | `886cc287a9b293c1bbcd447b937be71a08613a9f` |
| INTU | 252 | 2024-01-02 | 2024-12-31 | `ebae5358662d2608762c21c7652bb3a2ddeb51c8` |
| LRCX | 252 | 2024-01-02 | 2024-12-31 | `be2ff2a64acdeeb0def588d1796b1f753caa7a10` |
| META | 252 | 2024-01-02 | 2024-12-31 | `f5be3ab50849b70ab2fecbebde2d130d8f52a862` |
| MSFT | 252 | 2024-01-02 | 2024-12-31 | `219bc70a3387767ad6314c073592ad03b94cf402` |
| NFLX | 252 | 2024-01-02 | 2024-12-31 | `67fc0d441ff0b05840467083d89bd43dbbe7beab` |
| NVDA | 252 | 2024-01-02 | 2024-12-31 | `0a9ceb641301166ab07be26bafcb20d1bc76055e` |
| RMD | 252 | 2024-01-02 | 2024-12-31 | `befec2547ed28b803cdf0c53ee855f9ab883beae` |
| SAP | 252 | 2024-01-02 | 2024-12-31 | `c20e7d95e84b25996df09400f31006181c733ef1` |
| TSLA | 252 | 2024-01-02 | 2024-12-31 | `c0c0f4b20fa6ad8d81d0e3c9af00978f30d12dd4` |
| TSM | 252 | 2024-01-02 | 2024-12-31 | `d16239bba4087c69e50b5d387cfa63fc1a74fae7` |

A Git blob SHA is a content identifier, **not** a SHA-256 vendor proof,
instrument certification, original exchange price confirmation or a licence.

## Next original-source candidates, not yet imported or verified

1. Zenodo open research record
   https://zenodo.org/records/23401231 — 16 US stocks,
   2022–2024, source description states adjusted OHLCV and volume.
   The individual record's data licence, derived Yahoo history rights,
   all corporate-action conventions, exact original bytes and MD5 must
   be checked before ingest; repository access did not establish these.
2. Kaggle CC0 historic stock snapshot (archival 2017, *not current*):
   https://www.kaggle.com/borismarjanovic/price-volume-data-for-all-us-stocks-etfs/
   CC0 metadata does not independently certify upstream quote ownership.
3. Euronext official manual historical downloads:
   https://live.euronext.com/en/popout-page/getHistoricalPrice/IT0003128367-MTAA
   Source shows adjusted/nonadjusted options, but bulk automated,
   non-display analytics and historical redistribution rights need
   review under official Euronext market-data agreements.
4. ECB daily EUR FX, public official source:
   https://data.ecb.europa.eu/help/api/data
   This is the correct approach to FX, **not stock returns**.

## Independent review / acceptance checklist

- Evidence source rights **for local automated research**; original
  historic adjusted values and corporate-action events across splits,
  dividends and subscription rights; market ISIN/venue and trade units.
- Independently reconcile sample 5–10 securities versus a second
  official source; 61 consecutive lagged sessions plus 31 subsequent
  exchange sessions; delisted instruments and contemporaneous listing
  eligibility.
- Retain preregistered V2 unchanged; enforce 1,000 random-walk null worlds,
  top2-vs-bottom2, the equal-universe and 10,000 matched-K controls,
  confidence intervals and scenario spread/slippage sensitivity.
- Private **A** to verify actual fiscal event and broker charges
  separately. No automatic order route.

**Status:** SOURCE_INSPECTED_REJECTED_FOR_UNVERIFIED_RIGHTS_AND_ADJUSTMENTS.
No actual source data was written into GitHub.
