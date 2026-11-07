# Block B — assessment tecnico per revisione della PR

- **Base:** `main` dopo merge PR #1 (`e7d0852`), 58 test locali iniziali.
- **Scopo:** M3 e prima consegna M4. La revisione deve verificare codice e test,
  non attribuire valore di previsione ai punteggi.
- **Dataset default:** sette strumenti interamente sintetici.
- **Accesso a provider live:** NON eseguito in questo ambiente; richieste di rete
  soltanto via `investresearch-b collect` e mai in CI.

| Requisito | Evidenza | Stato |
|---|---|---|
| Isolamento dati personali | `.gitignore`, dataset sintetico | Implementato |
| Prezzi storici Yahoo facoltativi | `research_sources.py:collect_yfinance/parse_ohlcv` | Implementato, **non verificato live**; uso personale solo opt-in; licenza per uso aziendale non confermata |
| Fondamentali fonte primaria SEC | `research_sources.py:parse_sec_fundamentals` | Implementato, test mock; verifica live aperta |
| FX EUR da BCE | `research_sources.py:parse_ecb` | Implementato, test mock; verifica live aperta |
| Cache raw + hash | `research_sources.py:collect` | Implementato, test anticorruzione |
| Dati normalizzati point-in-time | `research_bundle.py` | Implementato, test lookahead/hash |
| Valuta omogenea nei ritorni | `research_screen.py:_fx_dated_prices` | EUR/USD senza interpolation; test |
| Indicatori rischio e momentum | `research_screen.py:_score_indicators` | Implementato, test valori attesi |
| Fondamentali nel ranking | `research_screen.py:screen` | Overlay opzionale limitato a net margin |
| Ranking ampio universale | `research_screen.py:screen` | Supporto fino a 5.000 item, non stress-testato live |
| Eventi macro e catalizzatori | `research_bundle.py:parse_events` | Registro documentale, nessuna interpretazione causale |
| Report consultabile | `research_screen.py:write_screening` | JSON/CSV/MD/HTML statico |
| Ricerca reale operativa | -- | **NON COMPLETA**: feed e mapping reali da validare |
| Predizione/out-of-sample | -- | Non implementata; nessuna performance promessa |
| Esecuzione trading | -- | Esclusa intenzionalmente |

## Accettazione

1. `python -m pip install -e '.[test]'` completato senza dipendenze a pagamento.
2. `pytest -q` e `python -m compileall -q src tests` superati.
3. `investresearch report` + dashboard Blocco A invariati.
4. `investresearch-b screen` produce file identici a input invariato.
5. `git diff` limitato al Blocco B, README, doc e CI.
6. Verifica GitHub CI della PR prima del merge; nessun merge automatico.
7. Nessun output demo spacciato per ricerca su prezzi reali.

## SEC annual research pilot — implementation increment

- `research_sec_pilot.py` links the SEC catalog and `companyfacts` by CIK,
  rejects future collection timestamps, incorrect official URLs, checksum
  mismatches and mismatched company identities.
- It only derives annual revenue, net income and arithmetic net margin from
  a coherent annual EDGAR filing. Missing SEC annual data remain reviewable
  gaps; unverified prices/sector/ISIN are not fabricated.
- CLI command `sec-pilot` is **opt-in**, today-only, at most eight explicitly
  selected tickers and spaced SEC requests. No secret or raw SEC payload is
  written to committed files or uploaded artifacts.
- End-to-end test fixtures use independently constructed SEC-like payloads,
  including future amendments, conflicting accessions, ambiguous tickers,
  tampered hashes, missing fiscal fields and negative margins. Offline CI
  never requires SEC credentials or network.
- Real-source smoke on main is a separate trusted workflow using the configured
  contact secret; **successful connectivity does not by itself certify this
  newly added report until its exact pinned version is exercised live**.
- M4 live-price ranking and broad cross-sector coverage remain pending.


### Confirmed SEC live integration (2026-11-02)

- Initial real SEC pilot found that official ticker catalog rows sometimes
  contain `exchange=null`. The parser now maps that to `UNMAPPED` and
  retains the valid CIK/ticker mapping.
- Pinned immutable commit `c70dbea756f8e20baadfe5bccc6d018d4f2f9262`
  passed the trusted SEC workflow: **10,423** catalog associations and **4/4**
  issuer annual evidence results, with independent SEC connectivity checks
  also passing. [Live evidence](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41429639471).
- The public source data are fetched with an explicitly authorized, rate-limited
  contact header, never committed. All original SEC response bodies remain on
  the temporary runner; only derived public information can be distributed.
- The live verification establishes a **small US annual financial-data pilot**,
  not a global coverage claim, complete price ingestion, investment ranking,
  industry comparability, or trading readiness.
