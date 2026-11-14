# R-007 — Correzione dell'esclusione del 15% e limiti dell'universo storico
**Data di valutazione:** 12 novembre 2026. **Classificazione: POST HOC / ESPLORATIVO.**

## Esecuzione verificata

La CI GitHub Actions del commit `75333e79`, run
https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/43121250055,
job `posthoc_real_15percent_jump_sensitivity`, ha completato con SUCCESS
il nuovo confronto sul dataset originale del primo studio. L'ultima run è
stata cancellata durante gli altri job per una commit successiva; il job
posthoc di quella run era già **SUCCESS**, con output numerico completo.

**Controllo delle tre sorgenti originali:**
- Aethereal original adjusted-price CSV SHA-256:
  `6480d9c288ae7521a6a44dbb75786cbec3a62149bcfaecc263999290fa30d020`.
- Current S&P roster SHA-256:
  `853f2fe3c4b126b6b251dbc7c81510de22c17167f2c0e646212e38e1cc45420f`.
- ECB EUR/USD original XML SHA-256:
  `e00ae31dccd722aa1edb5970252f82641c70a0c873e3a0556554259336043af1`.

Non si pubblicano prezzi, ticker, singole operazioni, dati del conto bancario
o dataset di un fornitore. V1/V2/V3 e il protocollo multiorizzonte
pre-registrato sono **immutati**.

La diagnosi sulla stessa versione dei dati ha verificato che l'intera
esclusione da 13/14/9 finestre (1/3/6 mesi) era dovuta a movimenti
giornalieri >=15%, **zero** a sedute mancanti:
https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/43094947324.

## Risultati numerici — solo proxy dei prezzi rettificati dal fornitore

| Indicatore | 1 mese | 3 mesi | 6 mesi |
| --- | ---: | ---: | ---: |
| Finestre originariamente complete | 24 | 5 | 1 |
| Finestre censurate con prezzo giornaliero completo, recuperate nel proxy | **13** | **14** | **9** |
| Finestre complete nel proxy post hoc | **37** | **19** | **10** |
| Rendimento medio netto TOP2 | **-1,439225%** | **-0,351907%** | **+4,857274%** |
| Rendimento medio netto same-K casuale | -0,103945% | +2,306810% | +5,579174% |
| Eccesso TOP2 meno same-K | **-1,335280 pp** | **-2,658717 pp** | **-0,721900 pp** |
| Intervallo bootstrap 95% eccesso (NON confermativo) | [-2,654824; -0,024278] pp | [-6,770172; +1,373625] pp | [-9,644785; +7,910037] pp |
| Censura per sedute realmente mancanti | 0 | 0 | 0 |

Valori netti di commissioni ipotizzate sul capitale teorico €10.000,
al netto del cambio ipotizzato ma **lordi delle imposte**.

Il primo studio strettamente fail-closed, basato solo sui fold senza
salti giornalieri >=15%, riportava eccessi -1,770827 / -0,408473 /
-6,377717 pp. Quelle medie non erano rappresentative di tutti i fold
maturati e non vanno confuse con le nuove medie proxy.

**Interpretazione:** nessun orizzonte mostra una sovraperformance media
della TOP2 rispetto al comparatore con identico K e identici costi.
Non equivale alla dimostrazione di "alpha negativo": gli intervalli
post-hoc non correggono data snooping, dinamica storica di identità e
licenza, selezione tra sopravvissuti, rettifiche non riconciliate o
correlazione delle selezioni tra orizzonti.

## Due difetti distinti e rispettivo stato

**Falso split da >=15%: mitigato e misurato nel pilot, non certificato
a livello di fonte.** Il proxy può ora valutare tutte le finestre
con sessioni complete senza buttare via veri crolli/rialzi. Non si
suppone che sia stato verificato se ogni movimento >=15% derivi
effettivamente da uno split o da una variazione economica: occorrono
corporate actions con data e fonte indipendente, raw vs adjusted,
dividendi e accadimenti di delisting/settlement. Non cambiare
retroattivamente la soglia nel protocollo storico congelato.

**Survivorship bias: NON RISOLTO.** Audit sulla fonte MIT storica
`kitata2/8765_sp500_pit` commit
`830c0128fc585131ede9d722958214e1208ff0fa`
(research membership only):
- 505 titoli all'inizio del 1 luglio 2021;
- 505 nel 18 agosto 2026;
- 614 ticker distinti presenti almeno una volta nel periodo;
- 95 dei 505 iniziali non presenti alla fine;
- i 40 del primo pilot risultano presenti alle 37 date storiche,
  perché il campione è scelto tra i componenti **ancora attuali**.
I 95 usciti non hanno una serie di prezzi/uscita autenticata nel pilot.
Senza quella copertura, ricostruire la semplice membership PIT non
basta a eseguire un test su una popolazione senza selezione ex-post.

L'archivio comunitario storico è per ticker, non un security master
PERMNO/ISIN stabile; il rischio di ticker recycling resta.

## Fonti alternative valutate e gate sui diritti

1. `Johnbrick123/sp500-data` pubblica un ampio archivio dichiarato
   point-in-time, inclusi delisted e corporate actions, ma nel README
   dichiara anche utilizzo di dati **CRSP** e non è presente una licenza
   redistributiva nel repository verificato. Pubblicazione su GitHub
   non certifica i diritti di usi industriali/privati o di data extraction.
   NON inserire automaticamente quel Parquet tra le fonti ammesse.
   https://github.com/Johnbrick123/sp500-data
2. HF Data Library offre dati gratuiti da IEX dal 7 marzo 2022 e
   scaricabili con account/API key, ma **solo academic/educational use**
   secondo le condizioni aggiornate, non per informare trading e
   decisioni d'investimento, e copre solo IEX, circa 2–3% del volume
   consolidato. Non sostituisce il pannello licensed PIT con cashflow.
   https://hfdatalibrary.com/pages/terms
3. `kitata2/8765_sp500_pit` MIT copre la sola composizione storica;
   non fornisce prezzi e dividendi finali.
4. Fonti per uno studio serio con delisted, CA, diritti e storico
   pluriennale richiedono una verifica documentale della licenza.
   Nessun acquisto è stato autorizzato o effettuato.

## Gate di accettazione per un test realmente investibile

Prima di qualunque conclusione operativa, occorre produrre:
- data originale congelata, SHA dei file, diritto esplicito di ricerca
  privata e uso in un workflow di decisione;
- universo storico as-of scelto prima dei rendimenti (non sopravvissuti);
- identità stabile e storica per ogni strumento, inclusi delisted;
- prezzi OHLCV originali, split, dividendi, acquisizioni, liquidazioni e
  corrispettivi finali verificati da almeno un'altra evidenza;
- stesso score B congelato a T, gate A su processo completo, costi
  comparabili, benchmark same-K e un genuino periodo di validazione
  indipendente dal periodo già usato per sviluppare;
- riproduzione quantitativa e giudizio dell'auditor indipendente su A.

**Verdetto:** primo difetto misurato e isolato con tutte le finestre;
secondo difetto rimane un **blocco esterno sui dati**, non correggibile
inventando prezzi o sostituendo licenze. `trade_ready=false`,
`predictive_edge_certified=false`; nessun ordine o merge.
