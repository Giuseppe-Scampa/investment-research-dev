# Investment Research Engine — architettura condivisa

**Versione architetturale corrente: V3.0.0** (baseline formalizzata il 3 novembre 2026).

Questa pagina e il **link stabile** a cui tornare per conoscere la specifica vigente. Il documento V3.0.0 non va riscritto dopo l'approvazione: nuove decisioni producono ADR e una nuova versione, mentre la roadmap può aggiornare lo stato del lavoro, sempre con evidenze.

- [Architettura V3.0.0 — baseline](V3.0.0.md)
- [Roadmap M1–M6, requisiti e gap](ROADMAP.md)
- [Versioning e change control](CHANGE_CONTROL.md)
- [Prompt di assessment per Claude e Gemini](ASSESSMENT_PROMPTS.md)
- [ADR-0001 — adozione della baseline](adr/ADR-0001-v3-baseline.md)
- [Riconciliazione assessment Claude/Gemini — 3 novembre 2026](ASSESSMENT_RECONCILIATION_2026-11-03.md)
- [ADR-0002 — requisiti V2 da recuperare (PROPOSTA, non approvata)](adr/ADR-0002-v3-1-recovered-requirements-proposed.md)

**Source of truth:** i file docs/architecture/ di questo repository pubblico contengono soltanto architettura e requisiti generici, senza dati finanziari personali. Eventuali implementazioni private e dati fiscali personali restano nel repository privato e in locale. Le due basi di codice hanno responsabilità diverse, ma la numerazione delle milestone è **unica**.

**Situazione:** V3.0.0 definisce la specifica completa, non certifica il completamento del codice. M1/M2 sono avanzati, M3/M4 e M6 parziali, M5 non realizzata. La CI verde misura i test presenti, non la completezza dell'architettura.

**Regola operativa:** prima di una nuova PR si individua il requisito e la milestone nel piano; la PR riporta prove, test e stato; variazioni di comportamento o perimetro richiedono ADR e, se rilevanti, una versione V3.0.1 / V3.1.0 / V4.0.0. Non spostare i requisiti fra M1–M6 senza decisione versionata.
