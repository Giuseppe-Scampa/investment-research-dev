# ADR-0003 — Neutralizzazione di riferimenti individuali nel repository pubblico

**Status:** Proposed — modifica di sicurezza applicata alla PR, revisione indipendente prima del merge.
**Date:** 2026-11-06.
**Context:** alcune note di stato e un esempio nella baseline V3.0.0 contenevano riferimenti a condizioni finanziarie o preferenze individuali in contrasto con R-011 e con la dichiarata neutralità del repository pubblico.

## Decision

- Generalizzare nel branch pubblico i riferimenti individuali, mantenendo invariati M1–M6, R-001–R-013, le regole di calcolo e i criteri di DONE.
- Correggere **soltanto** gli esempi individualizzanti nella baseline esistente; questa è un'eccezione di redazione di sicurezza alla regola di immutabilità, non una riformulazione dell'architettura.
- Aggiornare il digest Git bloccato nella release gate e aggiungere verifica automatica su documenti pubblici a CI, con esito bloccante se i riferimenti ricompaiono.
- Conservare documentazione del dossier personale esclusivamente nel repository privato; non copiarla in issue, output pubblici o report AI.

## Alternatives considered

- Lasciare riferimenti individualizzanti pubblici per proteggere l'hash originale: respinto, in conflitto con R-011.
- Pubblicare una nuova baseline neutra conservando la vecchia nel working tree: respinto, la vecchia resterebbe direttamente esposta.
- Riscrivere in modo distruttivo la cronologia Git: **non autorizzato** da questa modifica; valutazione separata dell'operatore.

## Consequences, boundaries and risks

Il cambio non modifica comportamento o perimetro tecnico, né certifica i dati reali. Lo storico remoto e copie/fork precedenti possono conservare versioni già esposte: il controllo opera sul contenuto corrente e non costituisce bonifica della cronologia. Non eseguire force push o cancellazione di storia senza approvazione specifica. La nuova impronta SHA della baseline diventa la sola consentita dalla gate.

**Affected requirements:** R-011, R-012; milestone trasversali.
**Tests/evidence:** test documentale e `tools/verify_v3_release_boundary.py` eseguiti nella CI della PR.
**Reviewer/approval:** in attesa di revisione indipendente della PR, nessun requisito eliminato o rilassato.
**Supersedes:** nessuna decisione architetturale; esplicita eccezione editoriale di sicurezza ad ADR-0001.
