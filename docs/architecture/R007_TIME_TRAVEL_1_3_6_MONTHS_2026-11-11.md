# R-007 — Replay storico: selezione al tempo T, esito dopo 1/3/6 mesi

**Stato 11 novembre 2026:** software implementato e collaudato su dati
INTERAMENTE SINTETICI. Non è stata eseguita né validata una strategia reale.

## Protocollo originale preregistrato

Il protocollo è stato registrato nel commit
`cd795504e08e72dc77411f453b5b789671cc90f4`, **prima** del codice e
dei relativi test, in
`config/backtest/v3_asof_multihorizon_1_3_6m_protocol_2026-11-11.json`.
Git blob SHA: `05a63cc0906c782b2909031b0bb1fe0d09ad76e4`.
Nessun protocollo preesistente V1/V2/V3 viene modificato o aggiornato a
posteriori.

## Come funziona la simulazione

1. Si scelgono le stesse date di decisione ex ante del V3, dal 2021 al
   maggio 2026. Le date non sono spostate in funzione dei prezzi futuri.
2. Per la data T si calcola **lo score del motore B originale** usando
   61 sedute di borsa antecedenti o uguali a T, con le esclusioni, il
   fattore liquidità e i vincoli del motore esistente. Le informazioni
   che diventano note dopo T non devono entrare nello screening.
3. Si congela l'intero insieme degli strumenti ammissibili, il loro ordine
   di ranking, i due strumenti prescelti e il relativo hash SHA-256.
4. Per ogni strumento, l'ingresso teorico è alla **prima chiusura EOD
   disponibile nella seduta di borsa successiva a T**. Non si assume che
   la chiusura sia un prezzo eseguibile.
5. Si calcola la ricorrenza esatta di **1, 3 o 6 mesi di calendario dalla
   data d'ingresso**, con regola di fine mese (31 gennaio +1 mese =
   28/29 febbraio), e si osserva la prima seduta di quello strumento
   a partire dalla ricorrenza.
6. Si calcola il rendimento netto della posizione ipotetica con
   €10.000 iniziali divisi in due quote, commissioni 0,19% per lato,
   minimo €7 per lato e costo cambio ipotetico 0,25% per lato su USD.
   Sono riportati la percentuale di rendimento e l'utile/perdita in EUR;
   commissioni bancarie/fiscalità effettive sono **non autenticate**.
7. Comparatore primario: rendimento atteso esatto di una selezione casuale
   di **due** strumenti dello stesso insieme storico, con identico capitale
   e identiche commissioni. Si aggiungono 10.000 portafogli casuali,
   confronto con liquidità nominale zero e intervalli bootstrap dei fold.
   Un benchmark esterno (es. MSCI World) richiede un'ulteriore serie
   indipendente verificata: **non è sostituito da un numero inventato**.
8. Per ogni orizzonte si riservano **prima dell'osservazione dei rendimenti**
   le finestre indipendenti, impedendo di contare più volte holding period
   sovrapposti. Le osservazioni a 1/3/6 mesi provenienti dalla stessa
   selezione T sono correlate e non costituiscono tre prove indipendenti.
9. Se un qualsiasi membro della coorte storica manca di una seduta,
   presenta un movimento >=15% non riconciliato oppure ha un delisting
   privo di cashflow accertato, la finestra maturata è **UNRESOLVED**.
   Non si sostituisce un titolo perdente, non si imputa zero/ultimo prezzo
   e non si promuovono a conferma statistica le finestre rimanenti.

## Comando sul Blocco B già esistente

Il comando opera su un bundle locale, già creato dagli importatori attuali
e contenente dati **autorizzati e non inventati**, in `data/private/`.

```bash
PYTHONPATH=src python -m investresearch.research_cli historical-1-3-6m \
  --bundle data/private/BUNDLE_ORIGINALI_REVISONATI \
  --output data/private/NUOVO_REPORT_1_3_6_MESI.json
```

Non modifica il bundle e non riscrive un report già esistente. I CSV
originali non devono essere pubblicati in GitHub né negli artefatti CI.
Il report JSON ha una sezione per ciascun orizzonte:
`independent_horizon_results[].folds`,
`as_of_anchor_audit`, rendimenti netti selezionati e casuali,
commissioni/spread ipotetici, date d'ingresso/uscita, risultati EUR e
conteggi di finestre incomplete.

## Evidenza ottenuta finora

Sul set di 24 strumenti **fittizi**, con tutti i dati presenti:
- **1 mese: 37** finestre complete indipendenti;
- **3 mesi: 18** finestre complete indipendenti;
- **6 mesi: 9** finestre complete indipendenti.

Rimuovendo artificialmente una seduta futura a un membro selezionabile:
- 1 mese: 36 complete, 1 maturata irrisolta;
- 3 mesi: 17 complete, 1 maturata irrisolta;
- 6 mesi: 8 complete, 1 maturata irrisolta.

Le cifre misurano solo il comportamento dell'algoritmo; non rappresentano
rendimenti di mercato. Le CI del motore B e il contratto indipendente A
sono verdi. Per 6 mesi, circa 5 anni di dati permettono soltanto ~9
finestre non sovrapposte: non si può soddisfare per magia la soglia
predefinita di 30 prove indipendenti.

## Vincolo per la prova su prezzi REALI

I dati da ammettere devono comprendere almeno ~20 strumenti inizialmente
ammissibili, prezzo/volume per ogni seduta necessaria alla finestra, ticker
e identità/ISIN/MIC storici, date di emissione e delisting, cambio EUR/USD,
rettifiche split/dividendi documentate e titolo/licenza d'uso compatibile.
Un insieme costruito soltanto dai vincitori sopravvissuti al 2026 soffre
di survivorship bias e **non è certificabile**.

Il Blocco B già supporta l'importazione offline di storici originali
FWB e Euronext con dichiarazioni dell'operatore. Un CSV pubblico non
prova autonomamente i diritti d'uso, le rettifiche o la disponibilità
point-in-time; non forzare `EXTERNAL` su dati ignoti e non riqualificare
dati reali come `SYNTHETIC`.

Euronext NextHistory distingue esplicitamente prezzi, dividendi e fattori
di rettifica come prodotti dati; l'esportazione web di prezzi storici
può costituire una **fonte preliminare** ma non è automaticamente
un'autorizzazione per un motore di backtest, né necessariamente consente
la profondità multiennale richiesta. Finché non arriva il lotto originale
ammissibile, la prova reale rimane **NOT RUN**.

## Definizione di completamento

- SOFTWARE: tre orizzonti e riuso dello score B, fonte SHA e ingresso
  ex ante, esclusione non opportunistica dei mancanti, costi, random-K,
  bootstrap, confronto B→A.
- BACKTEST REALE ESPLORATIVO: risultato numerico su archivi originali
  idonei, con anno/eventi controllati e limiti esplicitati.
- VALIDAZIONE PREDITTIVA: holdout realmente non visto, 30+ finestre
  indipendenti per orizzonte, PIT e corporate actions, robustezza
  costi/FX e verifica fuori campione. Non sostituibile dai test verdi.

**Nessun ordine, raccomandazione o compensazione fiscale è certificato.**
