# Versioning, ADR e change control — V3

## 1. SemVer della specifica, NON versione del software

Ogni baseline immutabile si chiama **V<MAJOR>.<MINOR>.<PATCH>.md**, per esempio V3.0.0.md.

- **PATCH**: chiarimenti, correzioni editoriali, fonti o criteri più precisi che **non** modificano il requisito e il suo esito di accettazione.
- **MINOR**: nuove capacità compatibili, integrazioni o esplicitazione di requisiti senza cancellare ciò che era richiesto.
- **MAJOR**: modifiche incompatibili di scope, rimozione requisiti, modifica numerazione milestone, confini di trust o criteri di DONE.

Una baseline pubblicata **non si sovrascrive**. Un documento candidato viene discusso via PR; dopo approvazione si aggiunge il nuovo file e si aggiorna solo il puntatore 'versione corrente' in README.md. Il versioning non sostituisce release/tag del codice.

## 2. ADR: obbligatori per decisioni architetturali

Percorso: docs/architecture/adr/ADR-NNNN-titolo.md.

Schema minimo: **Status** (Proposed/Accepted/Superseded/Rejected), **Date**, **Context**, **Decision**, **Rationale**, **Options considered**, **Consequences**, **Affected requirements**, **Tests/evidence**, **Reviewer/approval**, **Supersedes** (se pertinente).

**Nessun requisito scompare** perché un assistente lo ritiene non necessario, troppo oneroso o fuori MVP. Il suo stato resta MISSING/PARTIAL/BLOCKED finché un ADR approvato modifica esplicitamente la baseline. Una decisione tattica non diventa di default un taglio permanente.

## 3. Workflow obbligatorio

1. Aprire proposta con requisito R-xxx e milestone M1–M6 impattati.
2. Analizzare alternative, trade-off, effetti su costi, privacy, fonti e failure mode.
3. Creare ADR e, se altera specifica, nuovo file versionato in PR dedicata.
4. Far revisionare a un secondo soggetto/assistente indipendente; registrare rilievi e prove, non solo un parere.
5. Ottenere approvazione esplicita dell'utente per eliminare o modificare requisiti già concordati.
6. Aggiornare il puntatore corrente e ROADMAP; collegare PR codice e test; non dichiarare DONE senza le evidenze.
7. Preservare vecchia versione e ADR per ricostruzione cronologica.

## 4. Stato e progresso (ROADMAP.md)

Usare soltanto **DONE**, **PARTIAL**, **MISSING**, **BLOCKED_EXTERNAL**, **OUT_OF_SCOPE_APPROVED**.

Ogni riga ha id immutabile, requirement, owner/repo, stato, evidenza, criterio di uscita e prossima azione. Un numero di test crescente non giustifica percentuali di progresso arbitrarie. Ogni data/URL/file riportato deve essere controllabile.

**Stato di completamento software** e **stato di verifica personale** sono separati. Un estratto bancario assente non impedisce di completare moduli generici su fixture sintetiche.

## 5. Sicurezza e coordinamento multi-repository

- Questa cartella nel repository pubblico costituisce la baseline condivisibile con revisori esterni, senza dati personali.
- Il repository privato deve fare riferimento alla stessa versione e ai medesimi ID; può aggiungere allegati private-only senza alterare la semantica dei requisiti comuni.
- Vietato copiare in questo repository: nomi del titolare, capitali personali, numeri conto, screenshot, report privati, costi individuali, credenziali o dataset senza diritti di redistribuzione.
- Non abilitare merge automatici, trading, API a pagamento o dati reali nelle Actions pubbliche senza esplicita decisione approvata.

## 6. Log delle decisioni

| Data | Versione | Decisione | Evidenza |
|---|---|---|---|
| 2026-11-01 | V3 (accordo originale) | Due percorsi, M1–M6, separazione A/B/C, API non obbligatorie | Decisioni nella conversazione di progetto |
| 2026-11-03 | V3.0.0 | Baseline formalizzata senza riduzione dello screening globale | ADR-0001 |
| 2026-11-03 | Nessuna nuova versione | Correzione Prysmian minoritaria e continuità ISIN Fresenius come fixing implementativo | PR tecnica esistente; non ridimensiona la specifica |

| 2026-11-03 | Nessuna modifica alla V3.0.0 | Correzione D1–D4 e PR metadata CI, rilievi D5 e requisiti V2 ancora da valutare | CI pubblica 41736873470, 201 test; ADR-0002 Proposed |
