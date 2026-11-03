# Roadmap tracciabile — V3.0.0

**Data di revisione iniziale:** 2026-11-03. **Spec:** [V3.0.0.md](V3.0.0.md).
**Questa è una fotografia del lavoro verificato, non una promessa di ETA.**

Legenda: **DONE** completo ed E2E dimostrato, **PARTIAL** implementazione non ancora soddisfacente per tutti i criteri, **MISSING** assente, **BLOCKED_EXTERNAL** solo per validazione personale o dipendenze reali esterne, **OUT_OF_SCOPE_APPROVED** solo via ADR.

| Requisito | Milestone | Stato | Evidenza disponibile | Prossimo gate per DONE |
|---|---|---|---|---|
| R-001 anagrafiche, integrità, anti-lookahead | M1 | PARTIAL | Private Blocco A PR #2: quality, market_calendar, security_identity; 103 test CI | E2E con schema comune e serie reali autorizzate |
| R-002 fiscalità, redditi, vintage | M2 | PARTIAL | Private Blocco A PR #2: tax_engine, tax_netting, broker_import | Revisioni di interpretazione fiscale + copertura casi e strumenti richiesti |
| R-003 scenari A/B/C e costi | M2 | PARTIAL | Private: decision, cost_engine, broker_preflight, dashboard; test sintetici | E2E completo con caso anonimo realistico, no input inventati |
| R-004 fonti reali/provenance e rights | M3 | PARTIAL | Public Blocco B PR #2: SEC reale, BCE, ESEF validazione campionaria, manual local prices | Fonte prezzi reale autorizzata e affidabile per ricerca riproducibile |
| R-005 prezzi, corporate actions, FX | M3 | PARTIAL | Parsing, checksums, anti-lookahead; mapping Fresenius nel privato; gate >=15% e warning FX asincrono nel pubblico (CI 41736873470) | Corporate actions/FX/adjustment verificati su storici reali rappresentativi, non solo euristica |
| R-006 universo globale multi-asset | M4 | PARTIAL | SEC ticker discovery US ampia, campionamento hash non alfabetico (non rappresentativo); universo ancora candidato non classificato | Mercati non-US, classi alternative, mappatura, filtri tracciati |
| R-007 funnel e shortlist indipendente | M4 | MISSING | Documento obiettivo, nessuno screening ampio real-world validato | E2E centinaia -> 30–60 -> 5–7 -> <= 3 con ragioni/limiti |
| R-008 ranking multi-fattore | M4 | PARTIAL | Indicatori e scoring su demo 7 titoli fittizi; overlay margine SEC | Reali fondamentali, valutazioni, rischio, settori, controtesi, macro |
| R-009 AI gratuita e multi-provider | M5 | MISSING | Runner OpenAI commerciale legacy nel repo privato, non equiparabile a M5 | Validare provider free/quote/termini, creare multi-provider facoltativo e controlli fonti |
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

- Private PR #2 Blocco A: 103 test passati nella Actions run 41717867386 (ultimo esito controllato il 3 novembre 2026).
- Public PR #2 Blocco B: **201 test passati**, CI PR 41736873470 (verifica del 3 novembre 2026). Controllo governance PR eseguito con esito positivo.
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
