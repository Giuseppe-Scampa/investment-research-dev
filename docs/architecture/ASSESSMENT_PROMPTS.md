# Prompt di assessment indipendente — V3.0.0

Usare due assessment **complementari**, non la stessa istruzione copiata due volte. Le conclusioni devono citare file e righe/commit verificati. Nessun accesso a dati personali, API key o repository privati senza autorizzazione.

## Prompt A — Claude, architettura / implementazione / regressioni

Agisci come **revisore tecnico indipendente** dell'Investment Research Engine. Non proporre nuovi sviluppi prima di accertare la conformità all'architettura V3.0.0. Leggi:

1. https://github.com/Giuseppe-Scampa/investment-research-dev/blob/feat/block-b-data-screening/docs/architecture/README.md
2. https://github.com/Giuseppe-Scampa/investment-research-dev/blob/feat/block-b-data-screening/docs/architecture/V3.0.0.md
3. https://github.com/Giuseppe-Scampa/investment-research-dev/blob/feat/block-b-data-screening/docs/architecture/ROADMAP.md
4. https://github.com/Giuseppe-Scampa/investment-research-dev/blob/feat/block-b-data-screening/docs/architecture/CHANGE_CONTROL.md
5. PR pubblica: https://github.com/Giuseppe-Scampa/investment-research-dev/pull/2

Se il collegamento non è accessibile, scrivi "NON VERIFICATO" e indica esattamente quali file servono. Il privato investment-research-2026 non è necessariamente accessibile: non fare supposizioni su commit/test. Non usare una risposta di un altro modello come evidenza.

Confronta **M1–M6 e R-001–R-013** con funzioni realmente presenti, test, Actions, fonti/licenze, quality gate, time/as-of, gestione corporate action/FX, e privacy. In particolare: ricerca globale (non soltanto 16 titoli), M5 AI gratuita (non il vecchio runner a pagamento), M6 integrazione dashboard, distinzione fra DONE software e dipendenza Mediolanum per simulazione personale. Controlla se i nuovi moduli sono collegati al reale flusso E2E e non sono soltanto test unitari isolati.

Output richiesto:
- Tabella **R-ID | status DONE/PARTIAL/MISSING/BLOCKED_EXTERNAL | prova specifica (file:line o run) | gap | test di accettazione**.
- Massimo 5 difetti prioritari P0/P1, distinguendo bug comprovati da opinioni/rischi teorici.
- Difetti di sicurezza/dati e test di regressione consigliati con riproduzione minima.
- Valutazione della coerenza fra pubblico e privato *solo se entrambi accessibili*.
- Lista delle modifiche eventualmente soggette ad ADR o a nuova versione.
- Giudizio finale distinto: **MVP Decision 2026** vs **V3 completa**.

Non eseguire merge, non modificare la baseline o la roadmap da solo, non inviare ordini. Non inventare CI o disponibilità di feed. **I dati Mediolanum non sono un prerequisito per completare il software.**

## Prompt B — Gemini, completezza di prodotto / pianificazione / fonti

Agisci come **product architect e controrevisore metodologico indipendente**. Il tuo obiettivo non è confermare Claude ma cercare requisiti dimenticati, gap tra moduli, assunzioni nascoste o scope creep. Leggi la stessa architettura V3.0.0, CHANGE_CONTROL.md e ROADMAP.md usando i link qui sopra, quindi verifica per quanto possibile PR pubblica #2, README, test e sorgenti.

Ricostruisci il **flusso end-to-end**: universo ampio -> acquisizione autorizzata/point-in-time -> controlli -> valutazioni/rischio/fondamentali -> scoring/shortlist -> scenari A/B/C (in ambiente privato opzionale) -> AI free opzionale -> dashboard/audit. Verifica se la piattaforma copre davvero: più mercati e asset class, dati con licenze utilizzabili, corporate action e FX, controtesi e rischi, macro e geopolitica datate, vincoli etici minoritari vs prevalenti, M5 free multi-provider, no API premium obbligatorie.

Output richiesto:
1. Mappa di completezza **M1–M6** con prove / ASSENZE dimostrabili e dipendenze.
2. **Critical path** dei requisiti di sviluppo ancora mancanti, ordinati per impatto sul rilascio, non numero di test.
3. Due roadmap separate ma compatibili: **release tattica Decision 2026** e **release Research Engine V3 completa**, senza cancellare la seconda per accelerare la prima.
4. Matrice **rischio, probabilità qualitativa motivata, mitigazione, criterio di accettazione** (senza probabilità numeriche inventate).
5. Proposte ADR per ogni cambiamento di scope/architettura; distingui fix implementativo, decisione reversibile e cambio MAJOR/MINOR/PATCH.
6. Il **prossimo blocco implementabile** in una PR coerente, con deliverable, test e definizione di DONE.
7. Una sezione "Cosa renderebbe sbagliato questo assessment?", con fonti mancanti e incertezze.

Non assumere che il privato sia visibile; marca chiaramente il non verificato. Non inventare quotazioni, cronologia GitHub, connettori gratuiti o risultati test. Non richiedere un export bancario reale per completare l'architettura software; serve soltanto per il caso fiscale personale. Non eseguire ordini o merge.

## Protocollo di sintesi dei due assessment

1. Raggruppare i rilievi per R-ID, severità ed evidenza; evitare doppioni.
2. Verificare in GitHub le affermazioni riproducibili, non decidere per consenso fra modelli.
3. Ogni modifica che altera la specifica richiede ADR e versione successiva. Le correzioni conformi alla V3 richiedono solo PR codice + test.
4. Aggiornare ROADMAP con prova e stato, senza trasformare MISSING in OUT_OF_SCOPE per comodità.
5. Non promuovere ad acquisiti un provider dati, una classificazione fiscale o un servizio AI solo perché documentati in README.
