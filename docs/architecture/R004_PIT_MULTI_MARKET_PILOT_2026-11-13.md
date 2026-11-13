# R-004 — Point-in-time membership, 4-market 32-name technical pilot
**P0 software increment — 13 November 2026.** Branch: `feat/block-b-data-screening`.

This module is a **candidate-membership diagnostic**, NOT a historical price
backtest, a scientific point-in-time certification, an investment shortlist or
evidence of predictive value. All non-code test rows are intentionally FICTIONAL.

## Decision already agreed

Technical pilot: **8 ordinary-equity candidates per geography per historical
decision date** in four geographies: USA (NYSE/Nasdaq grouped together),
Italy (XMIL), Germany (XETR), France (XPAR). Exactly the earliest 12
date anchors of the **unchanged frozen V3** are inspected by default.

- The objective is source readiness, not achieving statistical power at N=32.
- Further historical validation target: 64, not yet instantiated or preregistered.
- No automatic expansion to 96 and no change to TOP2, its comparator or V3.
- Source venue exclusions and oil policy use only the supplied
  historical source snapshot; these values remain operator claims.
- Never replace a missing historical security with a present-day survivor.

The model uses the exact V3 common exchange calendar; per geographical
market it picks the latest *documented* membership snapshot not later than
the anchor and no older than 100 calendar days. It requires an original
publication date AND an original effective date no later than the snapshot.
An announcement effective next month cannot be represented as today's roster.

A deterministic hash of operator-declared seed, anchor, market, stable
security key and sector selects up to 8 names with a cap of 3 per sector.
The source CSV order cannot change the selection; actual outcome availability,
future prices, delisting events and subsequent source snapshots are not used
in the selection. **No future-data-based substitution** is implemented:
inadequate or stale membership blocks the relevant anchor.

This is a *diagnostic algorithm*, not a frozen V4 statistical protocol.
The explicit seed must be recorded in a versioned future preregistration
before any new outcomes are inspected. SHA-256 is an integrity checksum, not
a third-party timestamp or a licensed-source authentication.

## Actual public-source triage (source descriptions ≠ licences)

| Geography | Source already identified | Original historical evidence | Current gate |
|---|---|---|---|
| USA | Frozen community S&P interval ledger (kitata2/8765_sp500_pit, pinned by existing B code) | Retrospectively reconstructed ticker intervals, subject to recycling | **BLOCKED** stable issuer IDs, original contemporaneous index file, delist cashflows, source rights |
| France | Euronext quarterly CAC review 10 Jun 2021 (effective 21 Jun) | Dated official change notice says no CAC40 change | **BLOCKED** full baseline roster and every subsequent review; notice alone is not a full roster |
| Germany | STOXX 3 Sep 2021 DAX addition announcement (effective 20 Sep) | Primary-source historical 30→40 composition change | **BLOCKED** baseline 1 Jul 2021, full roster and subsequent changes; no pre-effective additions |
| Italy | Borsa Italiana FTSE index family information | Official descriptions and periodic review framework | **BLOCKED** authenticated dated 2021 full constituents and all subsequent changes |

Specific primary sources:
- France: https://www.euronext.com/en/about/media/euronext-press-releases/euronext-announces-june-2021-quarterly-review-results-cacr
- Germany: https://stoxx.com/dax-welcomes-ten-new-members/
- Italy: https://www.borsaitaliana.it/azioni/mercati/mercati-landingpage/indici.en.htm
- USA: https://github.com/kitata2/8765_sp500_pit

**Never treat index-change press releases as complete source snapshots**.
A full contemporaneous baseline plus all dated effective changes is required.
Modern recreated lists, Wikipedia edits and later revisions are only
research aids until cross-checked to timestamped original primary evidence.

**Market-data rights separately blocked.** Euronext's NextHistory is a
dedicated historical EOD provider (prices, volumes, dividends and adjustment
factors), NOT a free licensed source:
https://www.euronext.com/en/products-services/nexthistory .
Deutsche Börse distinguishes current on-screen information from its
historical Market Data Shop:
https://live.deutsche-boerse.com/en/kontakt .
No Yahoo chart endpoint, Stooq scraping, paid provider or permission-
restricted company data is used by this new pilot.

## What the operator has to provide (never commit to Git)

One original historic document and its separately reviewed UTF-8 CSV
transcription per market/snapshot. Store both under the ignored local
`data/private/pit/` folder and record distinct SHA-256 digests for both.

For each snapshot the JSON source pack contains EXACTLY:

- `market`: USA, ITALY, GERMANY or FRANCE;
- `snapshot_as_of`, `original_published_on`, `original_effective_on`;
- `source_kind`: OFFICIAL_HISTORICAL_SNAPSHOT_OPERATOR_TRANSCRIBED
  or ARCHIVED_HISTORICAL_SNAPSHOT_OPERATOR_TRANSCRIBED;
- `usage_rights`: OPERATOR_REVIEWED_PERSONAL_NONCOMMERCIAL,
  UNVERIFIED, RESTRICTED, or REQUIRES_PERMISSION;
- `source_url`: original HTTPS evidence location;
- `original_path`, `original_sha256`: verbatim source bytes and hash;
- `transcription_path`, `transcription_sha256`: independently stored
  CSV transcription and hash.

The enclosing JSON uses schema
`R004_MULTI_MARKET_PIT_CANDIDATE_PACK_V1` with a `snapshots` array.
Every CSV is strictly:

    security_key,isin,venue,sector,asset_type,oil_exposure,listing_date

`security_key` must be stable for the historical instrument/issuer, never
blindly a reused ticker. Date-vintage ISIN, exposure, sector, initial
listing date and official source must be independently reviewed by a
data operator. With no validated original 2021 membership document, do NOT
write a guessed source file and claim the pilot passed.

## Run after files have been legitimately obtained

    mkdir -p data/private/pit
    investresearch-b pit-multi-market-pilot \
      --pack data/private/pit/ORIGINAL_SOURCE_PACK.json \
      --private-root data/private/pit \
      --seed <64-lowercase-hex-of-predeclared-pilot-seed> \
      --first-anchors 12 \
      --output data/private/pit/PIT_AUDIT_01.json

Output is intentionally private because it includes individual security IDs
and ISINs. It records snapshot SHA-256, explicit per-geography blockers,
per-anchor drawn cohorts and chronological source diagnostics; **no prices,
performance, order instructions or fiscal approval**.

All outputs always set:
`research_ready=false`,
`historical_membership_independently_authenticated=false`,
`source_licence_independently_authenticated=false`,
`predictive_edge_certified=false`,
`trade_ready=false`.

Tests use only fabricated documents and symbols: deterministic selection,
row-order invariance, future snapshot nonleakage, future effective date,
invalid rights, stale snapshot, incomplete country, duplicate security
and future listing, hash tampering, private paths and no overwrite.

## Real-coverage go/no-go after the pilot

A technical draw of 32 names is not 32 authorized, priced, point-in-time
eligible assets. Real-source *admission* additionally requires independently
reconciled historic memberships and issuer/ISIN continuity, corporate
actions and terminal cash settlement, original adjusted EOD rights,
EUR conversion and 61 prior + 31 future exchange sessions as required
by the **separate** R-004 source-readiness audit.

No scientific V4 test or positive alpha claim is authorized until the full
input rights/identity/chronology gate is resolved and a V4 successor
protocol is recorded ahead of any new evaluation.
