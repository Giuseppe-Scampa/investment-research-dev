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
