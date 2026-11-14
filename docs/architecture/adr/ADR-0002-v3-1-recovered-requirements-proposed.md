# ADR-0002 — Recupero requisiti attribuiti alla V2 (proposta)

**Status:** Proposed — NON accettato, NON modifica la baseline.
**Date:** 2026-11-03.
**Candidate version:** V3.1.0 (da valutare solo dopo verifica della V2 originaria e approvazione).
**Affected requirements:** R-001, R-003, R-004, R-005, R-006, R-007, R-008, R-009, R-010, R-011, R-012.

## Contesto

L'assessment di Claude indica alcuni requisiti originari V2 non abbastanza espliciti in V3.0.0. Il testo integrale originale V2 **non è allegato a questo ADR**; pertanto il recupero è una proposta da verificare, non una prova di precedente approvazione.

## Proposta (nessuna decisione ancora approvata)

1. **Readiness stage** separati ricerca / shortlist / pre-negoziazione con uscita fail closed.
2. **Portfolio construction**: combinazioni di 2–3 strumenti, liquidità, rischio aggregato, concentrazione e tre profili simulativi.
3. **Asset-specific adapters**: dati minimi e limiti per ETF, ETC, ETN, obbligazioni e certificati; no confronto cross-asset numericamente incoerente.
4. **Backtest limitati / robustezza**: evitare dichiarazioni predittive e lookahead; eventuali walk-forward e stress su più regimi solo quando supportati dai dati.
5. **Supply-chain hardening**: dipendenze riproducibili, hash o lock verificati, scanner vulnerabilità e Actions pinned; compatibili con budget zero.
6. **AI rate limits e quote**: limiti dei servizi free realmente verificati, gestione 429, backoff con tetto, niente fallback su provider a pagamento implicito.
7. **Dashboard acceptance**: filtri, confronti pro/contro, rischi e scenari negativo/centrale/favorevole con evidenza e disclaimer.
8. **Riusabilità dopo 2026**: calendari anno-specifici, date fiscali e provider parametrizzabili; non fingere validità normativa 2027 automaticamente.
9. **Macro/geopolitica**: definire registro delle fonti, diritti, point-in-time e separazione fatti documentati vs ipotesi causali.

## Alternative

- Tralasciare i requisiti: non approvabile senza verifica dello scope originale.
- Inserire direttamente questi nove punti in V3.0.0: vietato dal change control.
- **Proporre un incremento compatibile V3.1.0** dopo verifica del testo V2, studio costi/rischi e approvazione esplicita: opzione raccomandata.

## Conseguenze

R-ID aggiuntivi e criteri di DONE andranno definiti nell'eventuale V3.1.0; la roadmap V3.0.0 resta valida e il lavoro su D1–D4 non è subordinato alla decisione.

**Review / approval:** PENDING. Non attribuire all'utente alcuna approvazione implicita. 
**Supersedes:** nothing.
