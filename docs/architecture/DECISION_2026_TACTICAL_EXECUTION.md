# Decision 2026 — utilizzo reale del Research Engine (tactical mode)

**Baseline:** V3.0.0 invariata, **R-006/R-007/R-008** ancora PARTIAL.
**As-of documentazione:** 2026-11-05.
**Obiettivo:** Scenario C con strumenti multi-asset, non un elenco scelto a mano
in chat. Implementazione: `investresearch-b tactical` nel repository pubblico
e `investresearch tactical-c` nel repository privato.

## Logica del percorso

1. **Sorgenti indipendenti:** discovery SEC e cataloghi di emittenti/borse
   per azioni, ETF UCITS, ETC, ETN, certificati e obbligazioni; verificare
   ISIN, MIC, settore, sottostanti, sovrapposizione Euro Stoxx 50 ed
   esposizione petrolio/oro. Un dataset selezionato manualmente è
   `SOURCE_DEFINED_COHORT_NOT_GLOBAL_INDEPENDENT_DISCOVERY`.
2. **Dati e diritti:** consolidare i dati in un bundle con
   `investresearch-b build --spec … --output …`; validare hashes,
   prezzo/corporate actions, 61 sedute consecutive, split, volume,
   BCE FX e limiti di autorizzazione. La chiave Alpha Vantage Free già
   testata [41930022872](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41930022872)
   consente un pilot FSLR 100 raw bars, **non** risolve l'ingestion
   adjusted per 200+ titoli. Evitare scraping non autorizzato.
3. **Ranking reale:** il comando `tactical` richiama **sempre**
   `research_screen.screen(bundle)`, non può ricevere una classifica
   CSV inventata; riutilizza `research_funnel._eligible` come controllo
   individuale senza indebolire il funnel R-007 da 200/100/40/6.
4. **Triage trasparente:** coda massima 12, copertura per tipo di strumento,
   scelta round-robin entro classi con score storici. **Nessun punteggio
   fra asset class è una previsione di rendimento**: non viene emessa
   una graduatoria globale né una raccomandazione.
5. **Fiscalità su ciascuna categoria:** il registro `FiscalRegistry` indica
   `REDDITI_DIVERSI` per equity, `REDDITI_CAPITALE` per guadagni ETF
   UCITS e `REVIEW_REQUIRED` per ETC, ETN, certificati salvo regola
   documentata sull'ISIN. Anche l'azionario resta
   `GENERIC_RULE_NOT_BROKER_VERIFIED`.
6. **Solo in privato — Scenario C:** `tactical-c` importa **due file
   abbinati per hash** (`TACTICAL_RESEARCH.json` e
   `BLOCK_B_SCREENING.json`), ricontrolla i campi e applica
   i costi e le regole fiscali private. Le simulazioni a -20%, -10%,
   0%, +5%, +10%, +20% e +30% sono **sensibilità matematica**
   a budget intero, non target/previsioni. I costi di spread/FX/FTT
   non verificati restano fuori dal calcolo e sono segnalati.
   È richiesto il saldo effettivamente residuo delle minusvalenze delle annualità pertinenti
   prima di fare affidamento sull'offset. Nessun ordine.
7. **Diligence finale:** esaminare valuation, catalizzatori, rischi
   e spread reali di intermediario; selezionare manualmente massimo 2–3
   strumenti solo dopo aver comparato casi downside/upside e scenario
   liquidità/no trade. Un report di ricerca non è un'autorizzazione a
   eseguire ordini.

## Comandi end-to-end

Nel repository **pubblico** (i file con prezzi reali e i rapporti
devono rimanere in `data/private/` o fuori dal repository):

```bash
# Il bundle reale va prima costruito da fonti effettivamente autorizzate:
investresearch-b build --spec data/private/research_spec.json \
  --output data/private/real_bundle_2026

investresearch-b screen --bundle data/private/real_bundle_2026 \
  --output data/private/decision_2026_screen

investresearch-b tactical --bundle data/private/real_bundle_2026 \
  --output data/private/decision_2026_tactical
```

Nel repository **privato** copiare *localmente* soltanto i due file JSON
del passo precedente nella directory ignorata dal version control
`data/private/imported_block_b/`. Non creare PR o artifact contenenti
dati di mercato raw o informazioni bancarie.

```bash
investresearch tactical-c \
  --research data/private/imported_block_b/TACTICAL_RESEARCH.json \
  --screening data/private/imported_block_b/BLOCK_B_SCREENING.json \
  --output data/private/decision_2026_scenario_c
```

Output: `TACTICAL_SCENARIO_C.json` e `TACTICAL_SCENARIO_C.md`.
Questo comando non richiede un import totale dello storico intermediario:
usa i parametri già presenti nel file di impostazioni privato come
**assunzioni dichiarate**, mai saldo verificato.

## Esecuzione oggi: ciò che è e non è verificato

- Alpha Vantage live FSLR: **connettività PASS**, 100 raw bars. Non è
  stata pubblicata una serie completa adjusted.
- SEC/ESEF/BCE: codice/probe reali esistenti, ma non forniscono da soli
  prezzi OHLCV con licenza/rischio corretti per tutte le asset class.
- `tactical`: algoritmo e test funzionanti; demo ufficiale
  `data/research/demo` deve produrre zero priorità, perché è
  **interamente sintetica**.
- **Mancano:** un bundle reale multi-asset con storico rettificato verificato,
  classificazione strumenti/diritti, eventuale identificazione materiale
  dell'indiretto petrolio, qualità fondamentale settoriale, spread e condizioni
  fiscalmente riconosciute da intermediario.
- **Non dichiarare investimento consigliato né R-007 DONE** fino alla
  presenza di queste prove.

## Sicurezza e governance

- `tactical` usa gli stessi blocchi etici/di portafoglio dello screen
  principale: evitare ulteriore oro, attività petrolifere primarie,
  e segnalare esposizioni indirette/materiali non verificate; alert
  Euro Stoxx 50.
- CSV protetti dalla formula injection; note Markdown escapate.
- Nessun download implicito, chiave API in pubblico, trasferimento di
  wallet in Block B, trade API, tasse certificate, budget inferito da
  messaggi AI o trasformazione della ricerca in ordini.
- **Il funnel permanente resta invariato:** la tactical mode
  rappresenta un percorso di ricerca delimitato, non un bypass dei
  gate globali.
