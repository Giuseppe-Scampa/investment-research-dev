# Block A V3 — assessment implementazione (distribuzione pubblica, dati dimostrativi)

**Controllo d'integrità:** riproduzione offline del report/della dashboard con fixture sintetiche. Non sono stati utilizzati provider a pagamento né dati di brokerage reali.

| Requisito | Evidenza | Esito e limite |
|---|---|---|
| Duplicate IDs in quote | `cli._source_rows` → `quality.read_strict_csv` | Gestiti, test di input duplicati |
| Mapping ISIN/venue/valuta | `quality.validate_instrument_mapping` | ISIN multisede consentito; ticker senza ISIN non è identificazione affidabile |
| Esclusioni | `constraints.instrument_constraints` | Oro/petrolio bloccati per nuovi acquisti; membership Euro Stoxx opzionale e solo warning |
| Fasi readiness | `quality.audit` + `readiness` | Recherche/shortlist/pretrade separate, nessun segnale buy |
| Date | `market_calendar` | Calendari scoping 2026; assenza regola fiscale broker esplicita |
| Quantità e indicatori | `analytics` | NaN/inf bloccati, RSI Wilder; FX EUR richiede dati allineati |
| Dashboard | `dashboard` | Stati incompleti in giallo, block in rosso; HTML escaped |
| Regole fiscali | `config/fiscal/rules_2026.json`, `tax_engine` | Per classe/evento, non validazione ISIN; ETC/ETN/CERT review-only |
| Posizioni e lotti | `positions.sale_cost_basis` | Solo lotti assegnati esplicitamente o costo medio bancario |
| Zainetto | `tax_engine.wallet_offset` | Separazione conti e anni, saldo dichiarato, non riconciliato |
| Costi e liquidità | `cost_engine` | Fee su importi, cassa comprensiva di commissioni, break-even; spread/FX/FTT se assenti incompleti |
| Confronto A/B/C | `decision.evaluate_case` | Esempio demo e scenari ipotetici, non prezzi eseguibili |
| Decision ledger | `decision.save_decision` | Hash input stabile, decisione ed outcome null |
| Riproducibilità | `tests/test_block_a_v3.py` | Stessi byte a parità di input e as_of |
| E2E | `investresearch report`, `investresearch-dashboard`, pytest | Verificati in locale, CI remota da osservare nella PR |

## Residui espliciti, non nascosti

1. Nessuna verifica contrattuale del trattamento fiscale dei singoli ISIN e nessuna conclusione automatica per ETC/ETN/certificati.
2. Date di regolamento modellate per mercati 2026 con calendario operativo circoscritto; data di riconoscimento fiscale non determinata.
3. Configurazione dati attuale parzialmente statica; prezzi validati ma non bid/ask eseguibili.
4. Prezzi di carico e lotti reali non forniti; il motore non può selezionare il metodo fiscale dell'intermediario.
5. Il modulo di bond non separa ancora in modo completo ratei/scarti dal prezzo di cessione.
6. I dati multivaluta devono avere base fiscale documentata in EUR, l'attuale simulatore non ricostruisce automaticamente cambi per data.
7. Nessun backtest predittivo validato; le vecchie percentuali di rendimento restano ipotesi di stress.
8. Stati da audit sono verifiche di processo, non autorizzazione al trading. Niente API del broker.
9. L'AI a pagamento esistente nel ramo main non viene attivata dal Blocco A; M5 è fuori perimetro.

## Decisione di merge

**Non eseguire merge finché CI GitHub non sia verde e i revisori abbiano verificato gli output e i limiti documentati.**

## Supplemento dopo le revisioni Claude / Gemini (PR #2, novembre 2026)

**Correzioni dimostrate e incorporate nello stesso branch:**

| Punto | Implementazione/Verifica | Stato |
|---|---|---|
| Guadagni e perdite 2026 | `tax_netting.net_realizations` con ordinamento giornaliero, compensazione stessa data/prior date, wallet 2022 successivo | CORRETTO, test di regressione |
| Plusvalenze ETF non compensate | Redditi di capitale e imposte stimate contabilizzate indipendentemente | CORRETTO, test di regressione |
| Confronto B solo imposta evitata | Include imposte generate, costi di vendita, effetto incrementale parziale e avvertenze; C mostra P/L al netto di imposte ipotetiche | CORRETTO, stima non certificata |
| Data quotazioni esistenti | Data obbligatoria, impossibilità di utilizzare prezzi futuri/stale/anno non supportato | CORRETTO, test di regressione |
| Ledger sovrascritto | `decision_ledger.jsonl` contiene cronologia persistente locale, registrazioni umane esplicite non eliminate | CORRETTO, test di regressione |
| Caso reale non caricabile | `investresearch report --case data/private/portfolio_private.json` e `.gitignore`; riconoscimento USER_SUPPLIED_UNVERIFIED | CORRETTO, test E2E |
| Euro Stoxx | Campi fonte/stato e warning su AXA/SAN, copertura generale `UNVERIFIED` evidenziata | CORRETTO, fonte secondaria |
| Break-even micro-posizioni | Ricerca di un limite superiore adattiva invece del precedente `prezzo*10` | CORRETTO, test di regressione |
| Classificazione fiscale legacy | Motore legacy legge le stesse categorie del `FiscalRegistry`, senza assumere `fiscal_status=eligible` come fonte normativa | CORRETTO, resta solo scenario sintetico |
| FIFO suggerito da Gemini | **NON adottato**: il regime amministrato prevede un costo medio ponderato (D.Lgs. 461/1997 art. 6(4)); per input reali si accetta solo il costo medio comunicato dall'intermediario | FALSO RILIEVO |
| Caso BTP descritto da Gemini | Corretta distinzione fra base fiscale 48,08% e imposta: evitare imposizione aggiuntiva sul residuo | FALSO RILIEVO |

**Punti residui:** deducibilità fiscale puntuale dei costi di FTT/spread/FX, basi fiscali estere, componenti di rateo/scarto dei bond, calendari > 2026, membership Euro Stoxx completa e tracciamento continuativo fra differenti esecuzioni Actions. I dati generali verificati non certificano classificazione e trattamento fiscale del singolo ISIN.

**Conclusione:** pronto alla revisione della PR **soltanto dopo CI remota verde**; nessuna autorizzazione a operare real trading o ad assumere 2026 saldo fiscale e book come verificati.
