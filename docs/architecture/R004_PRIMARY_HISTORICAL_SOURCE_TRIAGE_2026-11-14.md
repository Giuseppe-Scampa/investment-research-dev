# R-004 — Primary archive discovery and evidence limits (14 Nov 2026)

**Purpose:** P0 real source-discovery checkpoint for the 32-name technical pilot on XNYS/XNAS, XMIL, XETR and XPAR. This document and its JSON companion are metadata only, not authorized historical memberships, corrected EOD prices or an executable V4 protocol.

## Real documentary progress

| Market | Original provider evidence located | Earliest relevant material | Decision at 2021-07-01 | Rights / missing records |
|---|---|---|---|---|
| XETR (Germany) | [STOXX historical DAX archive](https://www.stoxx.com/end-of-the-day-data) lists monthly composition files in 2021 | January–December 2021 directory, including June/July | **PENDING**, must inspect actual June/July archive content, time-stamp and constituents before choosing | [STOXX access guide](https://www.stoxx.com/help) distinguishes guest, registered and licensed data; no blanket rights assumed |
| XMIL (Italy) | [Borsa Italiana historical index-capitalisation archives](https://www.borsaitaliana.it/borsaitaliana/statistiche/statistiche-storiche/capitalizzazioni/capitalizzazioni.htm), June and July 2021 | June 2021 and July 2021 month-end reports; July 30 basket document lists 40 names, no authenticated vintage ISIN master | June report is an **appropriate candidate** for July 1 only after the document, effective date, source rights and ISINs are checked. **July 30 report is not** | Access and downstream decision-use rights, full historical IDs, status of delisted issuers remain UNVERIFIED |
| XPAR (France) | [Euronext quarterly CAC review 10 June 2021](https://www.euronext.com/en/about/media/euronext-press-releases/euronext-announces-june-2021-quarterly-review-results-cacr) | No CAC40 changes effective 21 June 2021; [September 2021 review](https://www.euronext.com/en/about/media/euronext-press-releases/euronext-announces-annual-review-results-cac-family-sep-2021) records Eurofins addition / Atos deletion | **BLOCKED** until a full June baseline and issuer IDs are found. No-change notice cannot itself provide 40 names | Rights, baseline and full successive events still UNVERIFIED |
| XNYS/XNAS (USA) | Existing [kitata2/8765_sp500_pit](https://github.com/kitata2/8765_sp500_pit) retrospective index membership, pinned in Block B | Historical intervals include 2021–2026 | Candidate membership *only*, not exchange-certified PIT; ticker recycling and delisted payout unresolved | Pricing, corporate actions, identity continuity, right to intended use UNVERIFIED |

Machine-readable inventory (all false for rights and real admission):
`config/pit/p0_official_historical_source_candidates_2026-11-14.json`

Sources were identified in publicly available metadata/pages. The authoritative actual archive bytes have **not** been admitted to `data/private/pit` as original snapshots with SHA-256 and operator rights review; nor has a multi-country 2021–2026 original membership panel been reconstructed.

## Critical chronology / anti-survivorship constraints

1. The already-frozen V3 dates remain unchanged. The `pit-multi-market-pilot` examines only the **first 12** registered anchor dates by default.
2. Every candidate member must appear in a full original or independently reconciled historical index baseline at or before decision time. A contemporaneous *difference notice alone* does not establish the full historical set.
3. Corporate action announcements / index reviews are not effective until their documented **effective dates**. Announcements later than the decision cannot be used as earlier evidence.
4. An original public archive's current availability does not establish its original publication-vintage for an early backtest; dated original snapshots must be reviewed independently.
5. Original source bytes and their reviewed CSV/identity mappings stay under ignored `data/private/pit` and **never** in the public repository or CI artifacts. The currently checked-in catalog includes only publicly identifiable URLs and aggregate descriptions.
6. This work deliberately stops before selecting actual 32 names, reconciling delisted payouts, buying datasets or claiming alpha. Both private A strict replay and public B source readiness keep `trade_ready=false`.

## Next real-source acceptance gate

For **each geography**:
- inspect and securely retain original dated historical *complete* composition evidence, with independent source version, timestamp and operator-confirmed usage rights;
- reconcile historic ISIN/security master, including changes and issuer continuity before/after subsequent reviews;
- prevent replacing missing delisted price paths with living companies;
- acquire sufficiently long licensed EOD prices and independent corporate-action cashflows for the *entire* as-of sampled cohort;
- pass B `historical-source-readiness` and A's independent exact byte-level cohort replay.

**No V4 retrospective inference and no real capital allocation** are approved by source discovery alone.
