# Roadmap tracciabile — V3.0.0

**Data di revisione iniziale:** 2026-11-03. **Spec:** [V3.0.0.md](V3.0.0.md).
**Questa è una fotografia del lavoro verificato, non una promessa di ETA.**


## Stato esecutivo corrente — 2026-11-05 (integrazioni M1–M6)

La **baseline V3.0.0 è approvata** da ADR-0001, non è una release di software con tutti i gate passati. L'eventuale ADR-0002/V3.1.0 è ancora **PROPOSED**, non approvata. La presente matrice **non modifica milestone, scope, R-ID o criteri di DONE**. Lavoro svolto sul branch draft pubblico e sul branch privato, ancora non mergiati.

**Evidenza tecnica aggiornata:** Blocco B [CI 42087414991](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42087414991) **323 test PASS**, commit `ba3cf85d6075cf2a157619d91b16f884941e62fc`; Blocco A privato [CI 41934363975](https://github.com/Giuseppe-Scampa/investment-research-2026/actions/runs/41934363975) **123 test PASS**, commit `a15403cd0d8242d6a7e3e8b195d08bf53368af18`. Sono evidenze di codice e fixture, non certificazione fiscale o pre-trade.

| Gate V3 | Owner / repository | Stato | Evidenza corrente | Criterio concreto di accettazione ancora mancante |
|---|---|---|---|---|
| M1 / R-001 | A privato + B pubblico | PARTIAL | Parsing sicuro, hash, identità, calendario 2026, test negativi | E2E real-source identity/price/FX su contratto B→A e prova fail-closed |
| M2 / R-002,R-003 | A privato | PARTIAL | Fiscal registry, wallet e A/B/C su scenario sintetico | Copertura e revisione trattamento redditi/costi per asset e prove integrate; caso bancario personale è **gate esterno** |
| M3 / R-004,R-005 | B pubblico | PARTIAL — **BLOCCO CRITICO** | Alpha Vantage 100 barre RAW FSLR; SEC/ESEF/BCE; Xetra reale **5.548** listing validati | Fonte storica utilizzabile con diritti documentati, minimo 61 sedute continue, split/dividendi/FX e identità/venue riscontrati; test live su più asset class |
| M4 / R-006 | B pubblico | PARTIAL | [Xetra reale 5.548 e coorte 40](XETRA_LIVE_DISCOVERY_AND_PRICE_COVERAGE_PROBE_2026-11-05.md); SEC USA | Scoperta indipendente multi-venue con categorie/ISIN e rischi sottostanti verificati, ampliamento certificati (BFZ distinto), copertura prezzi |
| M4 / R-007,R-008 | B pubblico | PARTIAL | Funnel + scoring/tactical testati prevalentemente su fixture, nessun ranking finanziario reale della coorte 40 | Real-source screening e ranking con fondamentali/valuation/fattori/correlazioni/controtesi, 200+ globale → 40 → 6 → 0–3 (tattico più piccolo etichettato separatamente) |
| M5 / R-009 | B pubblico | PARTIAL — **NON BLOCCANTE per Decision 2026** | Ollama loopback opt-in, replay AI offline | Test live nel rispetto dei terms, benchmark provider gratuiti, fact-check materiale delle citazioni e quote protette |
| M6 / R-010 | B pubblico → A privato | PARTIAL | `tactical` e `tactical-c` con hash, fiscalità privata e dashboard separate | Un solo run E2E con source bundle verificato, dashboard/memo/ledger e report di esclusioni, rischi, limiti e provenance |
| Trasversali / R-011,R-012 | entrambi | PARTIAL | Repository separati, commit sintetici e source checks; baseline/ADR | Audit privacy/artifact/secret e diritti fonti; governance su diff e compatibilità cross-repo |
| Trasversale / R-013 | entrambi | DONE | Nessuna integrazione di trading automatico | Non regredire, nessun ordine |

### Sequenza operativa senza riprogettazione (work packages)

1. **P0 — Sbloccare M3/R-004,R-005 con dati reali.** La coorte Xetra da 40 è un *test di copertura dei provider*, NON un ranking finanziario. Cercare e verificare un feed storico effettivamente utilizzabile senza costo obbligatorio; provare prima un campione di ISIN EU e US in modo controllato, registrando entitlement, contratto d'uso, provenienza, adattamenti, calendari, split/dividendi, volume e FX. `NO_DATA_LICENSE` o `INCOMPLETE_NO_RANK` sono esiti accettabili e vanno mostrati senza fallback. Se le fonti gratuite non lo permettono, documentare precisamente il blocco: NON chiamare DONE M3/M4 né attivare abbonamenti.
2. **P0 in parallelo — Chiudere contratto e test d'integrazione M1/M2/M6.** Usare schemi e hash **già implementati** `screen → tactical → tactical-c`; predisporre una prova automatica inter-repository su bundle solo sintetico + casi negativi (schema incompatibile, fonte non autorizzata, currency/ISIN discordanti, fiscal status REVIEW_REQUIRED). Dati bancari mai nel repo pubblico. `tactical-c` resta analisi condizionale e non certificazione.
3. **P0 dopo i dati — Decision 2026 tattica:** sottocoorte multi-asset **derivata da regole di fonte**, non selezionata manualmente ad hoc; screening su storico verificato, comparazioni di rischio/concentrazione e correlazione, indicatori fondamentali/valuation pertinenti, evento/catalizzatore con data/fonte, controtesi. Evidenziare `REVIEW` per overlap Euro Stoxx 50, oro/petrolio indiretti ed ETC/ETN/certificati senza fiscalità per ISIN. Passare in privato ad A/B/C, inclusa opzione non operare e verifica deadline vendita/regolamento tramite intermediario. Nessuna forzatura di due acquisti.
4. **P1 permanente — M4 completo:** espandere dopo la modalità tattica verso discovery globale realmente misurata (denominatore, classi, venue, gap fonte) e funnel originale 200+/100+/40/6/0–3, senza sostituire la coorte di 40 al requisito globale.
5. **P1 — M6 definitivo:** report unico con traccia `source → ingest → quality → score → research priorities → decision scenarios`, prove replay, rischio aggregato, costi/spread/FTT/FX, privacy e audit. Separare il dossier intermediario personale dal DONE di codice generale.
6. **P2 — M5 AI gratuita e hardening:** solo dopo un percorso quantitativo leggibile; controanalisi non autorevole sui prezzi, controllo citazioni su fonte reale, rate limits, zero paid fallback. Concludere R-011/R-012 con verifiche CI/ADR e controllo dei dati/artifact.

**Regola di avanzamento:** ogni PR deve collegare R-ID/M-ID, commit, test, run live quando necessario, artefatti permessi, rischio residuo, esito fail-closed e criterio esplicito di DONE. Nessun aumento del numero di test, quantità di listing scoperti o connettore implementato modifica da solo lo stato di readiness. Niente nuovo ADR e niente merge senza controllo/revisione.

**Finestra Decision 2026:** mirare a una prima decisione di fattibilità entro la seconda metà di novembre **solo se** prezzi/fiscalità/broker superano i gate; se non passano, reportare un NO-TRADE verificabile e valutare lo Scenario B su posizioni esistenti. La completezza V3 permanente non deve bloccare una decisione tattica correttamente limitata.

---

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
- Il percorso **Decision 2026** può utilizzare in ambiente privato un saldo fiscale dichiarato dall'operatore, marcato come non verificato dall'intermediario; non è necessario ricostruire tutte le operazioni passate per iniziare confronti ipotetici A/B/C.
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


## Incremento cross-repo verificato — 5 novembre 2026, rischio/fiscalità/report

- **R-008 / M4:** nuovo `src/investresearch/research_risk.py`, comando `investresearch-b risk` su **identico bundle** dello screening e tactical. Analizza coppie con almeno 20 rendimenti sovrapposti, campione massimo 12, conversione EUR con avvertenze su fixing BCE/chiusure asincrone, storico 61 sedute per candidato. L'output include anche denominatori di copertura prezzi e warning per asset class. Solo prova sintetica; nessuna previsione o validazione di prezzo live. [CI pubblica 42120176014](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42120176014): **331 test superati**.
- **R-001,R-002,R-003,R-010 / M1,M2,M6:** il Blocco A privato utilizza i tre output B con controllo hash e produce dashboard privata unificata, correlazioni storiche e checklist ISIN con documenti, broker, spread e date fiscali ancora da validare. [CI privata 42120575513](https://github.com/Giuseppe-Scampa/investment-research-2026/actions/runs/42120575513): **143 test superati + smoke reale fra i repository superato**, esclusivamente su dati sintetici.
- **R-009 / M5:** importazione facoltativa e privata di report AI solo su ricerca societaria pubblica, con controllo dei riferimenti e hash; il testo generato non incide su rank, fiscalità, trading e non è sottoposto a fact-check automatico. Nessuna API AI a pagamento.
- **Stati immutati:** M1–M6 (e R-001–R-012) **PARTIAL** salvo prove future; R-013 **DONE**. B→A su dataset sintetico non equivale a run operativo reale. Fonte storici con diritti/aggiustamenti è ancora il blocco M3. Nessun merge o modifica della V3.0.0.

## 2026-11-06 — V3 software integrations wired and independently tested (release proof != real-market gate)

Software-only milestone integration update: *original V3.0.0 and ADR-0001 are unchanged*. Permanent Block B and private Block A are now connected across source screening, R-006 discovery (SEC/Xetra original catalog references), R-007 global funnel, tactical Decision 2026 research, R-008 historical risk, issuer/market-cap valuation multiples, dated macro/factor/geopolitical evidence, optional M5 2–4 public-only AI model reconciliation, M2 private broker case A/B/C, M6 dashboard and immutable-style hash audit ledger. Missing primary-source market inputs do not turn into guessed scores, factual citations, tax eligibility or trade recommendations.

Public B commit a32231bf0e5e8587b2a8e842ec8b7dc79f80332d; [CI 42236286556](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42236286556) **485 tests PASS**, live ECB/ESEF compatible, EODHD disabled/skipped. Private A commit 3edf4c7bb66cd8d5907cdc6313d214ee97510a17; [CI 42236371719](https://github.com/Giuseppe-Scampa/investment-research-2026/actions/runs/42236371719) **158 tests PASS** and full inter-repository smoke PASS, including two explicitly fictional original-schema market/currency/SEC/Xetra reference sets, valuation ratios, two public AI critique inputs and private tax A/B/C.

**Software path acceptance: CODE_INTEGRATED_AND_REGRESSION_TESTED for R-001–R-013.** This statement does NOT set all M1–M6 to DONE. The V3.0.0 gate to complete an actual permanent research engine still requires lawful real adjusted equities/ETF/ETC/ETN histories (including Europe), original point-in-time issuer fundamentals and public macro/factor claims authenticated, source-screened global >=200 market sample and independent 0–3 finalists, human citation/AI fact checks, privacy/licence audit and personalized broker statements for Decision 2026. Missing bank documents are an external PERSONAL validation gate, not an unfinished software code module. These are PARTIAL/NOT_VERIFIED as applicable.

Private independent R-ID acceptance matrix: [V3_SOFTWARE_INTEGRATIONS_ACCEPTANCE_2026-11-06.md](https://github.com/Giuseppe-Scampa/investment-research-2026/blob/feat/blocco-a-integrity-tax/docs/V3_SOFTWARE_INTEGRATIONS_ACCEPTANCE_2026-11-06.md). Source path remains no EODHD subscription, no paid API and no automated trading. PR #2 branches remain unmerged awaiting review.


## 2026-11-06 — R-009 manual-only free remote adapter increment

**Software change:** Gemini, Groq and OpenRouter now have optional fixed-HTTPS
single-request adapters in `src/investresearch/ai_remote_free.py` and CLI
`--invoke-free-remote`. Tests mock network and reject unknown/paid models,
unverified source citations, redirection and missing operator consent.
Groq Free tier's deprecated Llama 3.3 model is disallowed; the default
manual Groq smoke uses `openai/gpt-oss-20b`. OpenRouter permits
only a specific `:free` model, not dynamic fallback. Public synthetic-only
manual workflow binds three named GitHub Secrets; it is not scheduled and
cannot be launched via Actions UI before the workflow reaches `main`.

**Status:** CODE_INTEGRATED_AND_OFFLINE_TESTED; **M5/R-009 remains PARTIAL**.
No live API requests made in normal CI and no personal data sent to models.
The operator must inspect current account billing/free-tier status and run
a manual smoke only after review/release. Citation/content fact-check and
actual API success/quotas/cost are NOT verified by mock tests. No effect on
M3 market-data licensing, M4 global funnel, M2 tax, or orders (R-013).


## 2026-11-06 — R-004/R-005 & R-008: source-bound EU local import, portfolio risk, partial valuation

**Code increment (NO milestone promoted to DONE):**

1. `research_fwb_local.py`: non-network/manual local importer for original
   Deutsche Börse FWB `Price History` CSV. Exact Xetra/EUR/ISIN, date,
   locale, file SHA-256, source URL, user-attested **non-commercial** use and
   three adjustment choices are required. The exchange and adjustment flags
   remain **unverified by software**; partially adjusted inputs cannot receive
   a market rank. No data licensed for public redistribution, auto-download or
   paid API is introduced. Runbook:
   `docs/architecture/FWB_FREE_HISTORY_LOCAL_INTAKE_2026.md`.
2. `research_portfolio_stress.py`: full source-bound pairwise correlation
   matrix and fixed **equal-weight daily-rebalanced historical illustration**
   for at most three *already B-selected* risk candidates. It calculates
   aligned EUR EOD historical volatility, worst daily return, max drawdown and
   explicitly **assumed** -10/-20% parallel shocks. It does not calculate
   actual personal portfolio weights, options/certificates non-linear payoffs,
   forecasts, advice or broker suitability. A independently validates the
   new optional structured stress contract and displays it in the private
   dashboard.
3. `research_valuation.py`: permits `null` for missing optional issuer
   financial values. Calculates only ratios with actual cited operands,
   maintains explicit missing-fact inventory and numeric ratio count. The A
   side independently re-computes available ratios and rejects fabricated
   missing data. Never estimates price targets, future earnings or tax effects.
4. Private A fiscal regressions preserve the generic ETF UCITS distinction:
   positive gains as `REDDITI_CAPITALE` and realized losses as
   `REDDITI_DIVERSI`, without silently netting capital income with a wallet.
   Still requires **instrument/ISIN and tax-regime verification**.

**Acceptance:** SOURCE_PARSER_AND_RISK_CODE_TESTED_OFFLINE, not real-data
completion. Exact run SHA and test counts recorded by CI. No actual official
FWB CSV has been supplied or validated; no live securities screening based
on that provider, no independent corporate-action/legal authentication,
no real-world B→A run, no live AI. M1–M6 and R-001–R-013 statuses and their
DONE criteria are unchanged; European source licensing remains a source-
specific operator decision, not a software guarantee.
