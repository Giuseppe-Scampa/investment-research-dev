# ADR-0001 — Formalizzare e proteggere la baseline V3

**Status:** Accepted — formalizzazione di decisioni pregresse, 2026-11-03.
**Decisione:** pubblicare V3.0.0 come specifica canonica dei percorsi Decision 2026 e Research Engine permanente, senza ridurre i requisiti originari per accelerare la scadenza personale.

## Contesto

In assenza di una baseline unica, la roadmap del piccolo MVP fiscale aveva progressivamente rinominato M3/M4/M5 e confuso il completamento della decisione 2026 con il completamento della piattaforma. La sola CI verde non certifica le funzioni ancora mancanti.

## Decisione

- Conservare due percorsi, con milestone **M1 integrità, M2 fiscalità, M3 dati reali, M4 ricerca finanziaria, M5 AI gratuita opzionale, M6 dashboard/audit**.
- La piattaforma definitiva deve fare ricerca globale indipendente e non limitarsi alla watchlist preesistente.
- Il software deve poter essere completato con dati sintetici; la documentazione bancaria privata è dipendenza soltanto del collaudo personale.
- Adottare baseline immutabili SemVer, ADR, roadmap con evidenze e criteri di DONE; l'utente approva cambi di perimetro.
- Mantenere repo pubblico privo di portafogli, contratti e credenziali personali.

## Alternative considerate

- **Solo documenti sparsi nel repo:** rifiutata, genera perdita di contesto e divergenza.
- **Solo MVP fiscale 2026:** rifiutata come definizione di V3 completa; rimane una milestone tattica separata.
- **Versionare direttamente ogni modifica della roadmap:** rifiutata; la roadmap è uno stato di avanzamento, non una nuova architettura per ogni commit.

## Conseguenze e verifiche

I futuri sviluppi e i report di Claude/Gemini fanno riferimento ai requisiti immutabili R-001–R-013. Nessun nuovo requisito è “fuori scope” senza ADR approvato. Nessuna PR di coding cambia i documenti V3.0.0 retroattivamente. Stato iniziale e gap in ROADMAP.md.

**Evidence:** documento V3.0.0, CHANGE_CONTROL.md, review prompt e PR che introduce questa ADR.
**Supersedes:** ricostruzioni verbali non versionate; non elimina le scelte tecniche già documentate e compatibili.
