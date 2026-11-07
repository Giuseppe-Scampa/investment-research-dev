# R-004/R-005 — Deutsche Börse free historical prices: explicit local intake

**Scope:** software adapter integrated; an actual downloaded official history file
has **not** been supplied or tested. This is **not** a live market-data service,
not independent validation of adjustments, and not evidence for M3 DONE.

## Official source and rights

Deutsche Börse publishes individual-instrument `Price History` pages with
user-selectable venue and checkboxes for adjustments of **splits, dividends,
subscription rights**:
- [Historical prices example](https://live.deutsche-boerse.com/en/etf/ishares-core-msci-world-ucits-etf/price-history/historical-prices-and-volumes)
- [Explanation of price adjustments](https://live.deutsche-boerse.com/en/adjusted-prices)
- [Download price history terms](https://live.deutsche-boerse.com/en/disclaimer-en)

The official terms permit free use of FWB historical downloads **if the user
does not commercialize the data**; redistribution and value-added commercial
services are restricted. They explicitly disclaim accuracy and completeness.
**License scope depends on who is using the tool and for what purpose; the
software cannot certify it.** Do not use a company/commercial account assuming
that a personal non-commercial permission applies.

No website crawling, private API endpoint guessing, bulk automated downloads,
login automation, bypass of restrictions or hard-coded sample prices is
implemented. The operator manually downloads the original file after accepting
the stated rights, records its SHA-256 and original instrument URL, chooses
Xetra as venue and records the actual selected adjustment boxes.

## Import

Use `config/fwb_price_history_manual_example.json` as a **non-runnable
template**. All `REPLACE_` placeholders must be replaced from actual source
evidence. The original file must be a simple UTF-8 CSV; the mapping of three
headers `date`, `close` and `volume`, delimiter, decimal separator and
date format is deliberately **explicit**, because the site may change its
download schema and the parser must refuse to guess.

```bash
investresearch-b build --spec data/private/my-fwb-spec.json \
  --output data/private/fwb-source-bound-bundle

investresearch-b screen --bundle data/private/fwb-source-bound-bundle \
  --output data/private/fwb-source-screen

investresearch-b risk --bundle data/private/fwb-source-bound-bundle \
  --output data/private/fwb-risk
```

The parser requires: XETR venue, EUR trading currency, valid ISIN that matches
the approved original page, exact FWB HTTPS instrument history URL,
an operator acceptance of noncommercial use, UTC collection timestamp,
full raw-byte SHA-256, declared original CSV locale/header mapping, no
duplicate sessions, finite positive closes, valid nonnegative volume, and
bounded file length. **Date and numeric fields are never guessed**.

The resulting source metadata explicitly says:
- `fwb_data_verified_from_exchange=false`
- `historic_dividend_or_split_events_independently_verified=false`
- `FWB_OPERATOR_ASSERTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED` only when
  the user claims all three corporate-action options were selected.

If any option is not checked, the series is marked PARTIAL; if a declared
split is inside the screened period, the unchanged quality gate blocks
unadjusted splits.

**No ranked or trade-ready instrument is guaranteed.** Sector, ethical
exposure, listing, identity, licence, missing sessions, tax and the matching
corporate-action register still require independent human verification.
FWB is a potentially useful *local, bounded research source*, not a
certified free global historic feed. Institutional/commercial use requires
a separate explicit rights assessment.

**Acceptance outstanding:** original source CSV samples for different
asset classes, their download license assessment, actual 61+ valid sessions,
corporate-action positive/negative tests, independent comparison with an
official dated venue/corporate action reference, and end-to-end B→A run
under private access controls. None can be replaced by synthetic CI tests.
