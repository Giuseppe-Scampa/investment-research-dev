# Decision 2026 — first real Xetra catalog validation and 40-ISIN coverage probe

**Date:** 2026-11-05. **Scope:** R-006 DISCOVERY ONLY, R-004/R-005/R-007/R-008 still PARTIAL.
**Repository:** public Block B, draft PR #2. No merge, paid data, orders or vendor snapshot committed.

## Evidence actually executed

- [Official Xetra all-tradable-instruments download](https://www.cashmarket.deutsche-boerse.com/cash-de/Handel/Handelbare-Werte-Xetra/Downloads/xetra-downloads) is a public reference CSV, **not** historical market prices. Its website describes reference-data formats, not price/redistribution rights.
- [Deutsche Börse cash-market reference URL notice](https://www.cashmarket.deutsche-boerse.com/cash-en/Stay-Informed/circulars-newsletters/deutsche-boerse-circulars/Cash-Market-Readiness-Newsflash-Xetra-and-B-rse-Frankfurt-URL-change-for-the-All-tradable-Instruments-files-4764940) mentions automated retrieval paths; it does not grant a securities-price licence.
- The first real file caused a **fail-closed schema mismatch**. Unlike the synthetic fixture, the downloaded production reference starts with `Market:;XETR` (semicolon after the metadata label). Parser now explicitly accepts this documented observed variant while preserving hash, MIC, date, status, ISIN checksum and duplicate guards.
- [Successful real-source CI run 42086101417](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42086101417), acquisition **2026-11-05**, source update date **2026-11-05**, source raw SHA-256 **`b753edb4b9a109466b261f2d2fb5dfbca520e31fed783339774e46fe9814c2a8`**.
- Real observed output: **5,548 active instrument reference listings** and **6 inactive skipped**. Source classifications: **CS 1,754; ETF 3,198; ETC 206; ETN 390**. These are listings/identifiers, not fundamental/price-validated investment assets; Xetra ETF category alone does not prove UCITS.
- [Successful real 40-identity source-coverage probe run 42086773323](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42086773323) applied a stable deterministic SHA-256 order within each class. Allocation for **data-source diagnostics only**: **16 CS, 12 ETF, 6 ETC, 6 ETN**. Fixed sample-identity digest: **`f9934ab2ac91ce5a77248479459b0f7bf44d9827b63a3ac9bb993a9e44d10515`**. No identities/raw file were printed in public job logs.
- Source-coverage quota is a stratified sample, **not** an objective price/valuation/momentum screen and not independent global R-007 discovery. Some evident gold/oil/crypto/leveraged/short terms in labels are deferred from the sample, but name filtering **cannot certify indirect holdings, risk or ethical eligibility**. Even sampled identifiers are `REVIEW_REQUIRED`.

## How to reproduce and preserve the data privately

1. Download the authentic Xetra T7 CSV only under applicable terms; keep original bytes and retrieval timestamp in ignored `data/private/sources/`.
2. Generate `xetra_meta.json` with the **actual** source URL, original SHA-256, UTC acquisition time and explicit encoding, as instructed in [XETRA_DISCOVERY_INTAKE_2026-11-05.md](XETRA_DISCOVERY_INTAKE_2026-11-05.md).
3. Run `investresearch-b xetra-universe --raw ... --metadata ... --as-of 2026-11-05 --output data/private/xetra_discovery_2026-11-05`. The enhanced offline exporter writes the original full reference identity table and `XETRA_PRICE_SOURCE_PROBE_UNRANKED.csv` / `XETRA_PRICE_SOURCE_PROBE_MANIFEST.json` **locally**, with digests and `trade_ready=false`.
4. Do not upload vendor snapshots or any source-price CSV as public GitHub artifacts. CI only emits aggregate counts and SHA-256 evidence.

## Blockers that remain — do not claim Decision 2026 investment readiness

- **Zero 61-session licensed, split-checked and currency-aligned quote series validated for these 40 identities.** The Alpha Vantage FSLR pilot supplied 100 **raw** bars for a separately scoped US ticker; that is not this 40-ISIN European dataset.
- **Zero investment recommendations**, no verified issuer fundamentals/valuation, catalyst model, cross-asset correlations, bid/ask/spread or effective intermediario venue mapping from this T7 input.
- **Zero final ISIN-level Italian tax certifications** for ETC/ETN/certificates; ETFs require separate legal UCITS classification. No funds, wallet or account data leave private Block A.
- An Xetra snapshot does not cover the Frankfurt **BFZ certificates** feed. Never infer certificates from `WAR` labels. BFZ requires its own bounded ZIP/parser/issuer KID and source licence check.
- Next critical task: a *permitted* 61-session historical price source with corporate actions and FX for a **nontrivial subset** of the 40 IDs, then real `screen → tactical → tactical-c`. Missing or unverifiable series remain `INCOMPLETE_NO_RANK`, never synthesized.

**Result classification:** `DISCOVERY_REFERENCE_VALIDATED`; `UNRANKED_COVERAGE_PROBE_NO_SECURITY_SELECTION`; **NOT** `PRICE_SCREENING_VALIDATED`, `FISCAL_APPROVED` or `TRADE_READY`.
