# Input di posizioni esistenti — Block A V3

La fixture dimostrativa è `data/fixtures/investment_case_example.json` e contiene **dati inventati** per testare la logica. Per usare un caso locale, passare `investresearch report --case data/private/portfolio_private.json` con `fixture_kind: USER_SUPPLIED_UNVERIFIED`. Il file locale non viene caricato automaticamente dai workflow GitHub Actions.

Schema dell'oggetto:

```text
fixture_kind: SYNTHETIC_DEMONSTRATION_NOT_PERSONAL_HOLDINGS | USER_SUPPLIED_UNVERIFIED
as_of: YYYY-MM-DD (solo 2026 per il caso d'uso attuale)
account_id: identificatore di rapporto, NON il numero bancario reale
investment_budget_eur: decimal string
tax_regime: amministrato (unico regime simulato; dichiarativo rifiutato esplicitamente)
tax_wallets[]: {account_id, tax_regime, year, remaining_eur, verification_status}
existing_positions[]:
  {position_id, account_id, name, isin, asset_type, trade_currency, venue,
  lots:[{lot_id, quantity, purchase_date, tax_unit_cost_eur?}],
  sale_quantity, tax_cost_method, sale_lot_allocations?, broker_tax_unit_cost_eur?,
  reference_unit_price_eur, quote_date, ftt_scope, fx_bps, spread_bps}
new_investment:
  {name, isin, asset_type, quantity, purchase_unit_price_eur,
   hypothetical_sale_unit_price_eur, currency, venue, ftt_scope, fx_bps, spread_bps,
   scenario_kind: HYPOTHETICAL_NOT_FORECAST}
```

Usare stringhe decimali per quantità/costi. Non introdurre saldi, prezzi o cambi stimati come "ufficiali". In presenza di doppia valuta, preparare il costo fiscale **in EUR** e documentarne il tasso, invece di applicare il cambio corrente al costo originario.

`tax_cost_method: EXPLICIT_LOT_SELECTION` richiede una lista esplicita di lotti e quantità vendute che si riconciliano. Non presume che il metodo fiscale sia FIFO o LIFO. `BROKER_REPORTED_AVERAGE` richiede il valore in EUR comunicato dall'intermediario.

Il motore scrive `DECISION_COMPARISON.md`, `decision_comparison.json` e `decision_ledger.json`. La decisione umana resta `null`. Il confronto con nuove posizioni usa rendimenti ipotetici, non stime del mercato. Il software non consiglia un riacquisto né assume che una vendita/riacquisto sia priva di ulteriori aspetti fiscali.

## CLI attuale: input locale supportato

La restrizione iniziale descritta sopra è stata superata dalla revisione della PR:

```bash
mkdir -p data/private
cp data/fixtures/investment_case_example.json data/private/portfolio_private.json
# Modifica fixture_kind -> USER_SUPPLIED_UNVERIFIED e compila esclusivamente i dati autorizzati.
# Le posizioni reali accettano BROKER_REPORTED_AVERAGE, non lotti arbitrari.
investresearch report --case data/private/portfolio_private.json --output reports/generated
investresearch-dashboard --output reports/generated
```

`data/private/` e `portfolio_private.json` sono esclusi da `.gitignore`; **non** passare il file a GitHub Actions. Il percorso `--case` non viene caricato automaticamente da nessun workflow. Il report mostra `USER_SUPPLIED_UNVERIFIED` e non descrive il contenuto come fixture sintetica.

### Campi ulteriori e vincoli

- `quote_date`: obbligatoria per ogni posizione esistente; data `YYYY-MM-DD` non futura, non antecedente alla copertura del calendario supportato e distante al massimo `max_quote_age_sessions` dalla `as_of` (default **1 seduta**).
- `realization_date`: opzionale per simulazioni B e C; se assente viene usata **l’ultima seduta del mercato indicato non successiva ad `as_of`**, come riferimento puramente ipotetico. Una data esplicita deve essere una seduta supportata del 2026; per B non può precedere la quotazione. Non equivale a conferma fiscale del broker. La simulazione C richiede `venue` (MIC supportato) proprio per non inventare il calendario.
- `max_quote_age_sessions`: opzionale (intero) per un caso esplicitamente esplorativo, non sostituisce book e data fiscale dell'intermediario.
- `tax_cost_method`: per `USER_SUPPLIED_UNVERIFIED` è ammesso soltanto `BROKER_REPORTED_AVERAGE`, per evitare che la scelta arbitraria dei lotti diventi un imponibile presunto. La fixture `EXPLICIT_LOT_SELECTION` rimane esclusivamente dimostrativa.
- Il saldo `tax_wallets` rappresenta un dato **dichiarato**, non la quadratura automatica dell'intermediario.
- Prezzi, lotti e costo fiscale devono essere già espressi in EUR per il motore decisionale; il cambio fiscale storico non è ricostruito da questa versione.

Il risultato include `decision_comparison.json`, `DECISION_COMPARISON.md`, `decision_ledger.json` (ultima analisi) e **`decision_ledger.jsonl`**, storico append-only locale per ricerca e annotazioni umane. L'annotazione umana è una chiamata **esplicita** a `record_human_decision(outdir, decision_id, human_decision, observed_outcome=None)`; il report non inventa azioni. La semplice rigenerazione non cancella gli eventi precedenti. GitHub Actions conserva solo artefatti per singola esecuzione, quindi per uno storico persistente tenere la directory locale.

**Interpretazione degli importi:** B visualizza differenze nette della categoria `REDDITI_DIVERSI` dopo perdite correnti (stesso giorno o precedenti), utilizzo del vecchio zainetto, imposte attivate dalla liquidazione e frizioni di uscita. L'effetto incrementale di B **non è il rendimento del portafoglio**. C mostra il P/L di uno scenario deliberatamente inventato, dopo l'imposta simulata, senza aggiungere ancora il risparmio fiscale (che è già incorporato nella minor imposta).

## Confini del modello fiscale (review 2026-11-02)

- **Solo risparmio amministrato:** la modalità `dichiarativo` è rifiutata in modo esplicito, non approssimata con le regole dell'amministrato.
- Le date di realizzo sono chiavi ipotetiche riferite a sedute di mercato, **non** trade date, settlement date o date fiscali confermate.
- La simulazione applica perdite correnti antecedenti o della stessa seduta prima di utilizzare lo zainetto più vecchio. Questa **priorità tra saldi** è un'ipotesi del software e non è ancora attestata da un intermediario; il risultato rimane `ESTIMATED_NOT_CERTIFIED`.
- L'art. 6, co. 5, D.Lgs. 461/1997 si riferisce alle **operazioni successive** nello stesso rapporto; non è sufficiente a dimostrare l'ordine di compensazione tra transazioni eseguite nello stesso giorno.
