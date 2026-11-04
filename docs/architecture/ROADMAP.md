# Roadmap tracciabile — V3.0.0

**Data di revisione iniziale:** 2026-11-03. **Spec:** [V3.0.0.md](V3.0.0.md).
**Questa è una fotografia del lavoro verificato, non una promessa di ETA.**

Legenda: **DONE** completo ed E2E dimostrato, **PARTIAL** implementazione non ancora soddisfacente per tutti i criteri, **MISSING** assente, **BLOCKED_EXTERNAL** solo per validazione personale o dipendenze reali esterne, **OUT_OF_SCOPE_APPROVED** solo via ADR.

| Requisito | Milestone | Stato | Evidenza disponibile | Prossimo gate per DONE |
|---|---|---|---|---|
| R-001 anagrafiche, integrità, anti-lookahead | M1 | PARTIAL | Private Blocco A PR #2: quality, market_calendar, security_identity; 109 test CI (04/11) | E2E con schema comune e serie reali autorizzate |
| R-002 fiscalità, redditi, vintage | M2 | PARTIAL | Private Blocco A PR #2: tax_engine, tax_netting, broker_import | Revisioni di interpretazione fiscale + copertura casi e strumenti richiesti |
| R-003 scenari A/B/C e costi | M2 | PARTIAL | Private: decision, cost_engine, broker_preflight, dashboard; E2E sintetico realistico A/B/C con 2 vintage e 6 eventi | E2E completo con caso anonimo realistico, no input inventati |
| R-004 fonti reali/provenance e rights | M3 | PARTIAL | Public Blocco B PR #2: SEC reale, BCE, ESEF campionaria, prezzi locali con UTC/range sessioni/hashes (04/11) | Fonte prezzi reale autorizzata e affidabile per ricerca riproducibile |
| R-005 prezzi, corporate actions, FX | M3 | PARTIAL | Parsing, checksums, anti-lookahead; mapping Fresenius; gate >=15% e split_dates validati (anche split <15%); FX BCE asincrono non risolto | Corporate actions/FX/adjustment verificati su storici reali rappresentativi, non solo euristica |
| R-006 universo globale multi-asset | M4 | PARTIAL | Discovery SEC US ampia; funnel aggiunge conteggio delle classi, settori e venue effettivamente ordinabili, senza inventare identità/coverage | Mercati non-US e classi alternative con dati autentici, mappatura ISIN, prezzi/diritti, filtri tracciati |
| R-007 funnel e shortlist indipendente | M4 | PARTIAL | CLI di funnel offline: gate >=200 strumenti / >=100 ordinabili, pool 40, deep dive 6, finalisti provvisori 0–3 solo con diligence manuale; demo 7→0; 254 test CI | E2E reale multi-asset 200+ -> 30–60 -> 5–7 -> <=3, dati autorizzati, tesi/valutazioni comparabili e fonti verificate |
| R-008 ranking multi-fattore | M4 | PARTIAL | Indicatori e scoring su demo 7 titoli fittizi; overlay margine SEC | Reali fondamentali, valutazioni, rischio, settori, controtesi, macro |
| R-009 AI gratuita e multi-provider | M5 | PARTIAL | Modulo public-only opt-in: Ollama locale loopback e importazione offline di risposte Gemini/Groq/OpenRouter/Ollama; 230 test CI, nessuna API commerciale automatica | Test live Ollama; termini/quote e billing provider remoti; fact-check sostanziale fonti, hardening privacy e integrazione M6 |
| R-010 dashboard e audit unificati | M6 | PARTIAL | Dashboard separate Blocco A e B, decision ledger e report statici | Contratto dati B->A e dashboard unica provata E2E |
| R-011 privacy e trust boundary | Trasversale | PARTIAL | Public solo sintetico, private dossier locale, negative tests | Assessment globale PR/CI/artifact/data rights |
| R-012 versioning / governance | Trasversale | PARTIAL | Baseline V3.0.0, ADR-0001 e PR-body gate per R-ID/M-ID/versione (CI 41736873470) | Proteggere baseline e ADR anche tramite diff, verificare governance cross-repo |
| R-013 no automatic trading | Trasversale | DONE | Progetto di ricerca offline, nessuna API broker o ordini nei due rami | Conservarlo come gate in ogni nuova PR |

## Sequenza consigliata: obiettivo tattico e obiettivo permanente

**Track A, Decision 2026 (prioritario per calendario ma non riduce V3):**
- A1. Stabilizzare M1/M2 su fixture anonime, revisioni tecniche e test end-to-end.
- A2. Usare una fonte prezzi consentita e verificata per pochi finalisti, importando il contratto di ricerca M3, senza creare un feed universale fittizio.
- A3. Generare memo A/B/C con costi, rischi e incertezze evidenti; il caso personale rimane separato fino alla documentazione dell'intermediario.
- A4. Il dossier individuale verificato è **dipendenza esterna per le simulazioni personali, NON un prerequisito di sviluppo software**.

**Track B, Research Engine permanente:**
- B1. M3 prezzi storici autorevoli/leciti, corporate actions, FX, validazione provider.
- B2. M4 coverage europea e multi-asset, classificazione settoriale, universe-source, funnel, rank, controtesi; prove live senza dati personali.
- B3. M5 AI gratuita opt-in multi-provider, verifiche di citazione e assenza di costi obbligatori.
- B4. M6 report unificato, dati di provenienza, audit e rilascio completo V3.

## Evidenza CI e limiti

- Private PR #2 Blocco A: **109 test passati**, CI PR [41826154840](https://github.com/Giuseppe-Scampa/investment-research-2026/actions/runs/41826154840) (4 novembre 2026); caso sintetico R-003 con 2 vintage e 6 eventi, tassonomia Oil & Gas allineata.
- Public PR #2 Blocco B: **254 test passati**, CI PR [41869669069](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41869669069) (4 novembre 2026). Gate prezzi, R-009 opzionale e R-007 funnel offline con coverage/esclusioni esplicite.
- Entrambe PR aperte. Nessun merge del corpus V3.0.0 all'origine di questa roadmap.
- La CI testata riguarda i casi implementati, NON i milestone ancora parziali o mancanti.

## Come aggiornare il piano

Per ogni PR indicare esattamente: R-ID, M-ID, baseline architetturale, test, evidenza di sorgente/live se applicabile, regressioni e privacy, status prima/dopo. Se un requisito cambia, creare un ADR, passare il change control e pubblicare una nuova versione della V3 (senza modificare V3.0.0).

Vietato assegnare DONE perché un utente ha caricato un documento: DONE si riferisce alla funzionalità software, la documentazione privata si controlla nel percorso personale.

## Audit indipendenti Claude/Gemini — triage 3 novembre 2026

La revisione di Claude ha identificato D1 (vocabolario Oil & Gas), D2 (soglia split 40%), D3 (asincronia fissazione FX BCE), D4 (sottoinsieme SEC alfabetico), D5 (etichetta 'fundamental score' eccessiva), D6 (test count stale).

- **D1**: implementato; valori `primary`, `direct`, `predominant` bloccati; `minority` review, `indirect/material` review e no rank finché la quota non è quantificata.
- **D2**: mitigazione implementata; gate `>=15%` per salti close-to-close con test split-like 3:2, 4:3, 5:4. **Non** validazione di corporate action; falsi positivi e split minori possibili.
- **D3**: mitigazione documentale: il fixing BCE di riferimento e la chiusura azionaria USA non sono simultanei; serve per vero P/L intraday una convenzione di mercato/FX diversa e verificabile.
- **D4**: implementato sottoinsieme hash stabile con tracciabilità nel manifest; è **discovery subset** e non campione statisticamente rappresentativo.
- **D5**: ancora aperto, chiarire/rinominare overlay `net_margin` come euristica senza backward-incompatible rename non governato.
- **D6**: corretto in questa roadmap con la CI corrente.
- **Governance**: enforcement su metadata PR (V3.0.0, R-ID, M-ID, change class); protezione automatica della baseline ai diff e policy dipendenze ancora aperte.

[Audit e confronto delle evidenze](ASSESSMENT_RECONCILIATION_2026-11-03.md). [ADR-0002 proposto](adr/ADR-0002-v3-1-recovered-requirements-proposed.md) raccoglie funzioni che Claude attribuisce alla precedente V2; **non** sono state inserite retroattivamente nella baseline V3.0.0 né date per approvate senza confronto con il testo originale e consenso.

## Incremento verificato — 4 novembre 2026

- **R-003 / M2:** prova E2E sintetica su 3 posizioni, 2 vintage, 6 eventi 2026; verifica aritmetica B/C, non-compensazione capital income, rigetto di data riconoscimento incoerente e saldo wallet manipolato, preflight non trade-ready. Fonte in repository privato: `docs/R003_SYNTHETIC_E2E_2026-11-04.md`. Stato **PARTIAL** in attesa dei restanti requisiti e delle verifiche fiscali.
- **R-004/R-005 / M3:** per OHLCV manuali, blocco di timestamp non UTC/futuri/precedenti alla quotazione più recente, date split malformate/duplicate/future, stop allo score per split dichiarati anche sotto il 15%. Lo storico reale con diritti comprovati e corporate actions controllate **non** è ancora validato; stato **PARTIAL**.
- **R-007 (funnel globale)** era **MISSING** alla data di questa revisione; il nuovo incremento qui sotto lo porta a **PARTIAL** (solo algoritmo e test sintetici). **R-009** resta **PARTIAL** senza prova live del modello. V3.0.0 e ADR-0001 immutati.

## Incremento verificato — 4 novembre 2026, R-009 / M5

- Gateway AI **facoltativo** `src/investresearch/ai_counteranalysis.py`, avvio manuale dalla CLI `investresearch-b ai-countercheck`. Unico provider chiamabile: Ollama in **loopback** con opt-in esplicito, senza proxy, redirect o provider fallback. Nessuna API commerciale preconfigurata, obbligatoria o usata in CI.
- Confronto **offline** di risposte etichettate Gemini, Groq, OpenRouter o Ollama; etichetta dichiarata dall'operatore, non certificazione di free tier o provenienza.
- Input limitato a ricerca societaria pubblica con check `as_of`/data fonte, registri di ID, citazioni riferite soltanto a ID disponibili, filtri privacy *best effort*, documentazione e output locali ignorati da Git. I contenuti dei documenti e le citazioni NON sono fattualmente verificati dal motore.
- **Evidenza:** CI [41842478740](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41842478740), **230 test superati**, nessuna chiamata AI in Actions; esempio end-to-end interamente sintetico `config/ai_public_review_example.json` + `config/ai_public_response_example.json`.
- **Per DONE:** prova locale Ollama documentata, valutazione costi/termini delle API gratuite prima di eventuale live integration, verifica sostanziale citazioni su documenti autentici e integrazione M5→M6. R-009 **PARTIAL**, R-007 ora **PARTIAL** con solo funnel sintetico, non completo. Nessuna modifica a V3.0.0 o ADR-0001.

## Incremento verificato — 4 novembre 2026, R-006/R-007/R-008 / M4

- `research_funnel.py` e `investresearch-b funnel` applicano limiti parametrizzabili compatibili con V3.0.0: ≥200 candidati e ≥100 ordinabili, research pool 30–60 (default 40), due diligence 5–7 (default 6), finalisti 0–3 **soltanto con revisioni manuali documentate**, mantenendo tutti gli output `trade_ready=false`.
- Non si riempiono quote artificialmente; gli strumenti incompleti vengono esclusi con ragioni esplicite. Diversificazione per settore, conteggi reali per mercato/classe/settore, hash della ricerca, protezione CSV/Markdown e directory private per input esterni/manual review.
- Test su **250 candidati interamente sintetici**, non 250 emittenti reali: `254 passed` [CI](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41869669069). Demo ufficiale da sette strumenti correttamente produce **nessuna shortlist**.
- **R-007: MISSING → PARTIAL**, senza dichiarare screening globale completato. **R-006/R-008: PARTIAL** invariati per mancanza di copertura reale multi-asset, comparabilità fondamentali, valuation e verifica di catalizzatori; R-004/R-005 ancora limitati ai prezzi con diritti non verificati. V3.0.0/ADR-0001 invariati.
- Guida e gate: [R007_FUNNEL_RESEARCH.md](R007_FUNNEL_RESEARCH.md).

## Incremento 4 novembre 2026 — account readiness e prezzo pilota R-004/R-005

- Connettore **opt-in singolo simbolo** `investresearch-b alpha-pilot` per
  Alpha Vantage `TIME_SERIES_DAILY` free `compact` (ultime ≤100 osservazioni
  **raw**, NON split/dividend-adjusted). La chiave è letta **solo**
  da `ALPHAVANTAGE_API_KEY` locale; mai in codice, report, output, Actions o
  URL di provenienza. Una richiesta HTTPS, no retry/fallback, solo
  `data/private/` o percorso esterno, nessuna promozione a ranking.
- Input e output verificati con parser rigoroso, symbol match, date non future,
  OHLCV coerente, hash raw/normalizzato, limite byte, rifiuto rate limit e
  dichiarazione legale/qualitativa `NOT_TRADE_READY`.
- Il pilot non è stato ancora eseguito contro un account/API reale: richiede
  **l'utenza gratuita e il consenso esplicito** dell'operatore; non certifica
  licenze di uso non-display, storico rettificato, ISIN/MIC o trading.
- Matrice utenze e ordine di creazione:
  [ACCOUNT_AND_SOURCE_READINESS_2026.md](ACCOUNT_AND_SOURCE_READINESS_2026.md).
  Per ricerca SEC/BCE non occorrono nuovi account. Gemini/Groq/OpenRouter sono
  **successivi e opzionali**, così come Euronext/Cloudflare AI/Oracle.
- Il percorso **Decision 2026** può usare il saldo 2022 di circa **5.000 €
  dichiarato dall'utente**, con status diverso da `BROKER_VERIFIED`, senza
  richiedere il replay completo dei movimenti bancari per iniziare A/B/C.
  La verifica fiscale finale dell'intermediario resta necessaria prima di
  fare affidamento su compensazioni reali.
- Stati canonici invariati: R-004/R-005/R-006/R-007/R-008/R-009/R-010
  **PARTIAL**; V3.0.0/ADR-0001 invariati. Per R-007 `DONE` serve ancora
  almeno un funnel **reale** multi-market e multi-asset, non un test 250 synthetic.

## Riscontro live e piano di esecuzione — 5 novembre 2026

- **Alpha Vantage FSLR:** [GitHub manual run 41930022872](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41930022872)
  conclusa con `success`; i log confermano **100 sessioni RAW non verificate**,
  integrità del formato e nessun CSV pubblicato. Primo **pilot di connettività**
  reale: R-004/R-005 **ancora PARTIAL** fino a rettifiche corporate actions,
  provenienza certificata, licenza e riproducibilità.
- **Calendario indicative, utenze e gate:** il documento operativo versionato
  [INTEGRATION_EXECUTION_PLAN_2026-11-05.md](INTEGRATION_EXECUTION_PLAN_2026-11-05.md)
  separa Decision 2026 (prima A/B/C 1–2 settimane, verifica 3–5)
  da V3 completa (8–14 settimane con fonti adeguate); nuove API AI sono
  opzionali e successive alla stabilizzazione del contratto dati.
- La chiave Alpha Vantage è già nel secret GitHub (inserita dall'operatore):
  non esportare né leggere dati grezzi o segreti nel repository pubblico.
  **R-007/M4 non è DONE**: 250 fixture sintetiche non sostituiscono
  un universo realmente analizzato e multi-mercato.

## Decision 2026 tactical bridge e seconda fonte dati — 5 novembre 2026

- Blocco B `investresearch-b tactical` usa lo screening originale, i
  gate per singolo ISIN di R-007, e il registro fiscale; classi
  EQUITY/ETF_UCITS/ETC/ETN/CERTIFICATE, nessuna ricerca globale
  dichiarata senza universo autentico, nessun `trade_ready`.
- Blocco A privato `investresearch tactical-c` accoppia il report di
  priorità con lo screening sorgente tramite hash, identità, score,
  provenienza e **riproduzione dell'ordine deterministico**; simula
  commissioni, rendimenti ipotetici e fiscalità in privato. Non riporta
  un elenco d'ordine o prezzi eseguibili.
- [Runbook B→A](DECISION_2026_TACTICAL_EXECUTION.md), test in Blocco A e
  [valutazione fonti](REAL_DATA_PROVIDER_TRIAGE_2026-11-05.md).
- Nuovo `twelve-pilot`: client **opt-in** Basic solo US XNAS/XNYS,
  100 barre, `adjust=splits` richiesto e NON certificato,
  mai alimentato automaticamente nel ranking. Unit test tutti offline.
- **Il nuovo feed live NON è stato chiamato**: manca la chiave Twelve Data.
  Il pilot Alpha Vantage FSLR era riuscito con 100 barre RAW,
  ma non basta per un universe di centinaia di strumenti.
- Stati invariati: R-003/R-004/R-005/R-006/R-007/R-008/R-010
  **PARTIAL**. Solo R-013 DONE. Nessuna modifica a V3.0.0/ADR-0001.
