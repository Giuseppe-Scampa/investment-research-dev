# Piano di integrazione V3.0.0 — revisione 2026-11-05

**Documento operativo versionato; non modifica la baseline V3.0.0 o gli ADR.**
Questo piano distingue **software implementato**, **run live completati**, **dati
utilizzabili con diritti verificati** e **decisione di investimento**. Le date
sono stime indicative di calendario, non ETA contrattuali o lavoro automatico.

## Primo traguardo live — Alpha Vantage

- [Workflow manuale 41930022872](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41930022872):
  `workflow_dispatch` su `main`, completato **success** il
  4 novembre 2026 23:00 UTC.
- Il job `source-diagnostic` ha confermato
  `FSLR 100 RAW unverified sessions`, con parser e checksum della raccolta.
  Non c'è stato upload del CSV. Non ci sono prove di
  `TIME_SERIES_DAILY_ADJUSTED` o `outputsize=full`, né certificazione di
  condizioni non-display, rettifiche, data quality o possibilità di
  comparare 200+ strumenti in produzione.
- **R-004/R-005 restano PARTIAL**: la prima connettività live è provata.
  Un test del provider non è una convalida del ranking o della licenza.
- La chiave è stata fornita direttamente dall'operatore come secret di
  repository; il codice non deve estrarla, copiarla né pubblicarla.

## Sequenza, condizioni di avvio e stime di impegno

Le finestre assumono sviluppo e revisione **con continuità** e disponibilità
di fonti lecite. Non è stato pianificato alcun acquisto di dati o cloud.

| Track | Lavoro successivo | Integrazioni e credenziali | Effort indicativo | Gate verificabile |
|---|---|---|---|---|
| P0 M3 | Altri 2-3 pilot e analisi limiti RAW/FX/corporate actions, verifica uso dati | Alpha Vantage già attiva; SEC e BCE senza account | 2–4 giorni lavorativi | Prezzi fonte, as-of, corporate action/FX e licenza distinti in audit |
| P0 M6 | Contratto dati hash/provenienza B→A con rifiuto di dati non validati | Nessun account | 3–5 giorni | E2E sintetico pubblico→privato, nessun dato bancario nel pubblico |
| P0 M2 | Decision 2026 A/B/C con saldo fiscale ipotetico/non verificato in ambiente privato, calcoli fiscali/costi e alternativa non operare | Nessun nuovo account; eventuale controllo saldo bancario solo prima della decisione | 5–8 giorni | Report riproducibile e revisione fiscale esplicita |
| P1 M3/M4 | Mappatura US+Europa ISIN/venue/classi; fonte storici corretti e diritti; catalogo 200+ | SEC/BCE; analisi Euronext o altra fonte, non abbonarsi automaticamente | 8–15 giorni + tempi esterni | Evidenza reale indipendente con provenienza e denominatori di copertura |
| P1 M4 | Ranking settoriale, valuation, esposizioni, fattori di rischio, controtesi, funnel real-world | Nessuna API AI necessaria; corporate actions e feed autorizzati | 8–12 giorni | 200+→40→6→0–3 su fonti vere senza quote inventate |
| P2 M5 | Ollama locale + Gemini Free + Groq Free; opzionale OpenRouter, Cloudflare Workers AI | Ollama senza account; Gemini/Groq solo al collaudo; OpenRouter dopo decisione comparativa | 4–8 giorni + 3–6 per fact-check | Modelli non incidono sul rank/tasse, costo zero, citazioni verificate |
| P2 M6 | Dashboard unica, report sorgente→shortlist→decisione, audit e hardening finale | Nessuna nuova utenza | 6–10 giorni | E2E integrato, controlli privacy/diritti e governance cross-repo |

Gli effort sono **non necessariamente additivi**: alcuni task si sovrappongono,
altri restano bloccati da diritto d'uso, disponibilità del feed o qualità del
dato. `271 passed` misura regressioni implementate, non percentuale di
completamento. Gli account cloud NON risolvono la mancanza di dataset.

## Finestre indicative (as-of 2026-11-05)

- **Decision 2026 — prima versione A/B/C leggibile:** 1–2 settimane di
  lavoro attivo, **12–20 novembre** se non emergono criticità al contratto
  B→A. **Versione utile per una decisione con prezzi e fiscalità verificati:**
  circa 3–5 settimane, **fine novembre–prima metà dicembre**. Prima di
  negoziare verificare il saldo fiscale residuo presso l'intermediario, categoria dei
  redditi e condizioni operative. Data di riferimento prudenziale per la
  decisione: **non aspettare il 31 dicembre**.
- **V3.0.0 — MVP di ricerca su fonti reali:** circa 4–7 settimane di
  sviluppo attivo, **inizio–fine dicembre**, **solo se** viene risolta
  rapidamente l'origine di prezzi rettificati e il diritto d'uso.
- **V3.0.0 — completamento di tutti i gate (M1–M6, privacy, AI, audit):**
  circa **8–14 settimane**, **gennaio–febbraio 2027**. Il percorso critico è
  M3→M4 e non il provisioning delle API AI. Senza dati licenziabili e
  comparabili non esiste una data credibile per R-006/R-007 DONE, e deve
  rimanere PARTIAL senza un ADR esplicito che ne modifichi il perimetro.

Queste finestre presuppongono dedicazione regolare. Capacità intermittente,
revisione esterna, provider rate limits e audit fiscali possono estenderle.

## Attivazione altre integrazioni

1. **Ora:** SEC EDGAR, BCE FX, fonte ufficiale emittenti/ESEF;
   nessuna nuova credenziale. Alpha Vantage: tenere per poche validazioni,
   non come unica fonte del funnel. Il `TIME_SERIES_DAILY_ADJUSTED` è
   Premium; nessun upgrade automatico.
2. **Dopo il contratto dati e un primo bundle reale:** Ollama locale (senza
   credenziali) come primo benchmark opzionale, senza bloccare M2.
3. **Successivamente:** creare una chiave **Gemini Free** e **Groq Free**
   solo alla vigilia dei smoke test R-009; mantenere quote e fatturazione
   disabilitata; esclusivamente ricerche societarie pubbliche.
4. **Solo se aggiunge valore:** OpenRouter free come terza opzione remota
   e/o Cloudflare Workers AI. Non serve aprire account Oracle.
5. **Fonte europea/licenziata:** negoziare o attivare solo dopo aver
   stabilito che le fonti pubbliche non permettono ranking corretto; una
   licenza dati non viene sostituita da una chiave AI.

La pipeline quantitativa e fiscale deve funzionare anche senza Ollama,
Gemini, Groq e OpenRouter. V3.0.0 e ADR-0001 rimangono invariati.
