# Decision 2026 — Xetra reference discovery (R-006, no price ingestion)

**As of:** 2026-11-05. **Status:** offline importer implemented; live Xetra CSV **not yet validated**. R-006/R-007 remain PARTIAL. No merge, trade, paid account or price-ranking promotion.

## Official primary sources

- Tradable Instruments Xetra:
  https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra/xetra
- T7 Cash Instrument Reference Data Guide, Section 5.2:
  https://www.cashmarket.deutsche-boerse.com/resource/blob/4591780/4a5a7f89c8d8b15538a6dc83e3e7c0c5/data/T7_R.14.0_Cash_Markets_Instrument_Reference_Data_Guide_Version_1.pdf

The official site displayed approximately 5,600 Xetra listings on 2026-11-05, including separate shares, ETF, active ETF, ETC and ETN categories. The CSV specification has semicolon-separated records, line 1 Market: XETR, line 2 Date Last Update: DD.MM.YYYY, line 3 column headers. Required fields: Product Status, Instrument Status, Instrument, ISIN, Mnemonic, MIC Code, Settlement Currency, Instrument Type. The vendor guide documents source type codes CS/ETF/ETC/ETN/OTHER/BOND/WAR/SR/FUN. These codes are instrument reference classifications, not a proof of fund legal status, tax status, price history or execution venue at Mediolanum.

## Offline use and provenance

1. Open the official Xetra website and manually download **T7 (XETR) All tradable instruments**. Check the actual vendor terms for intended usage before retaining/processing the source. Never commit vendor CSV to the public repository.
2. Store original bytes locally under ignored data/private/sources/t7-xetr-allTradableInstruments.csv. Preserve the vendor first two metadata lines. Compute SHA-256 on the original bytes.
3. Create ignored data/private/sources/xetra_meta.json with the ACTUAL values from this download. Example schema (replace all example evidence):

    {
      "provider": "XETRA_T7_INSTRUMENT_REFERENCE",
      "source_url": "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/0447d5f72a1ca9cd3f00a6bd5f8805cc/data/t7-xetr-allTradableInstruments.csv",
      "sha256": "REPLACE_WITH_ACTUAL_64_DIGIT_LOWERCASE_SHA256",
      "retrieved_at_utc": "2026-11-05T09:05:00Z",
      "encoding": "utf-8-sig"
    }

The URL and UTC acquisition time above are **examples**, not a statement that any file was collected. For a source with independently confirmed different byte encoding, explicitly set encoding to latin-1; no silent fallback is allowed.

4. Run on the Block B feature branch:

    sha256sum data/private/sources/t7-xetr-allTradableInstruments.csv

    investresearch-b xetra-universe --raw data/private/sources/t7-xetr-allTradableInstruments.csv --metadata data/private/sources/xetra_meta.json --as-of 2026-11-05 --output data/private/xetra_discovery_2026-11-05

The importer performs **zero network requests**. It verifies URL, SHA-256, UTC retrieval date <= as-of, Xetra last update date <= retrieval, XETR MIC, Active statuses, ISIN checksum, currency, original instrument class and duplicated listing identities. Unknown types are excluded and counted. It does not infer asset-class returns or tax compensation rights.

## Outputs and safeguards

- XETRA_UNRANKED_CANDIDATES.csv: ISIN, instrument, mnemonic, venue, currency, conservative type, discovery-only status.
- XETRA_DISCOVERY_MANIFEST.json: acquisition/source hashes and dates, class counts, skipped rows, normalized CSV SHA-256 and limitations.
- Real vendor data stays under ignored data/private or outside the repository; public tests contain only synthetic T7-format rows.
- Max file 20 MB, max rows 100,000; output directory cannot silently overwrite existing files.

## Crucial limits

- Xetra ETF does not imply UCITS; classify it ETF_LEGAL_STATUS_UNVERIFIED, never automatically as ETF_UCITS in Block A.
- Xetra WAR and OTHER do not prove Italian tax treatment for certificati. ETC/ETN categories similarly do not prove compensability.
- Names cannot validate indirect oil/gold exposure, leverage or overlap with Euro Stoxx 50.
- Listing data has NO historical prices, total returns, bid/ask quotes, liquidity quality, corporate-action validation or catalysts.
- Public availability of reference data is not a license for redistribution or automated commercial usage; clarify terms separately.
- This is broad independent reference discovery for the European market, not a globally representative or survivorship-free backtest universe.

## Remaining operational gates

1. Run and inspect the importer against one **actual** official Xetra CSV, including any schema/encoding variations. Log evidence privately.
2. Match identities against Euronext Milan and issuer KID/prospectuses to determine exact legal product and underlying risk; add the certificate universe separately.
3. Verify lawful split-adjusted historical OHLCV feeds for a diverse set of instruments and confirm 61 sessions, corporate actions and corporate issuer fundamentals.
4. Build the Block B bundle and run tactical using source-checked prices; then transfer only paired hashed reports to private Block A tactical-c.
5. Validate actual Mediolanum ISIN-level tax treatment and wallet balance, spread, commission and executable venue before final candidates.

R-006/R-007/R-008 and fiscal pre-trade readiness remain PARTIAL. No shortlist, trade, automatic data refresh, altered funnel threshold or assumption of a vendor license is asserted.
