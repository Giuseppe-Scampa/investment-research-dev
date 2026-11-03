# Assessment Claude / Gemini — riconciliazione evidenze 3 novembre 2026

**Baseline:** V3.0.0 immutabile. **Repository verificato:** pubblico
`investment-research-dev` branch `feat/block-b-data-screening`.
**CI dopo le correzioni:** [run 41736873470](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41736873470), 201 test verdi, incluso check PR metadata.

## Metodo

La revisione di Claude è una fonte di ipotesi e test indicati dall'autore, non un'attestazione del codice privato. D1, D2 e D4 sono stati verificati sui sorgenti pubblici e corretti con regressioni; D3 è una limitazione reale della convenzione temporale, documentata; D5 rimane un rischio di naming e interpretazione. Le affermazioni di Gemini non dimostrate da codice, CI e contratto dati non sono state promosse a fatti.

| Rilievo | Stato | Prova o limite |
|---|---|---|
| D1 oil taxonomy | FIX APPLICATO | `constraints.py` e `research_screen.py`; test vocabolario in `test_block_b_evidence_hardening.py` |
| D2 split <=40% | MITIGATO NON RISOLTO COMPLETAMENTE | review per salti >=15% e test 3:2, 4:3, 5:4; manca fonte corporation actions validata |
| D3 FX BCE vs US close | LIMITAZIONE DOCUMENTATA | Conversione EUR su reference fixing di calendario uguale, non sincronizzata intraday |
| D4 alphabetic SEC subset | FIX APPLICATO | subset hash deterministic with manifest, NOT statistico/rappresentativo |
| D5 net-margin overlay name | APERTO | Il punteggio non è valutazione fondamentale generalizzata; revisione output/schema necessaria |
| D6 outdated test count | FIX DOCUMENTAZIONE | 201 test (run sopra) |
| Governance PR R-ID/M-ID | PARZIALE | CI ora valida i campi PR e ADR/versione su class=Architecture, ma non ispeziona ancora diff né branch protections |

## Osservazioni Gemini che NON costituiscono verifiche

- Conteggi 96/192 sono superati dai test correnti; la PR privata è stata verificata anche dopo l'allineamento della tassonomia Oil & Gas, con 104 test passati nella CI 41737383649. Non sono stati verificati dati fiscali personali.
- M5 multi-provider **MISSING**, non parzialmente implementata in questo repository. Un runner legacy a pagamento in privato non equivale alla milestone.
- La presenza di unit test fiscali non certifica normativa, broker o correttezza del portafoglio reale.
- `data/private/` e un checksum riducono rischio di pubblicazione accidentale, ma non costituiscono garanzia generale di privacy o autenticità dell'estratto bancario.
- Parser ESEF validato numericamente su campioni non equivale a fondamentale IFRS "production-ready" per centinaia di emittenti.
- Un audit append-only hashato o una dashboard "institutional-grade" sono ipotesi di roadmap, non capacità già contrattualizzate.
- Le date Q1/Q2 2027 suggerite sono **proposte**, non tempi accettati o dimostrati dal throughput di sviluppo.

## Gap architetturali tuttora reali

P0: fonte prezzi storici con diritti dimostrabili; corporate action, valuta e orari affidabili; contratto dati research->decision; report non-trade-ready con date/ISIN.

P1: universo non-USA e multi-asset, funnel verificabile da centinaia a shortlist e ranking multi-fattore; AI gratuita opzionale M5; dashboard/report di M6 integrati.

P2 (proposte): maturazione multi-periodo oltre il 2026, sicurezza dipendenze, test backtest ridimensionati, gestione quote/429 AI, UX dashboard, specifiche quantitative per ETF/ETN/obbligazioni/certificati. Verificare V2 originale e ADR-0002 prima di versionare come V3.1.0.

Il caso Decision 2026 e la ricerca permanente restano **due track distinti**. Dati bancari reali sono richiesti per la decisione fiscale personale, NON per il completamento del codice su fixture.
