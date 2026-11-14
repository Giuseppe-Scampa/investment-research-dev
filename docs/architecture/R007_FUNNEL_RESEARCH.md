# R-006 / R-007 / R-008 — Funnel di selezione verificabile

**Baseline:** V3.0.0 (non modificata); milestone **M4**. 
**Implementazione:** `src/investresearch/research_funnel.py`; CLI `investresearch-b funnel`.
**Stato:** R-006 `PARTIAL`; R-007 `PARTIAL` (meccanismo implementato, nessuna prova
di screening globale reale); R-008 `PARTIAL`. **Non si tratta di un titolo comprabile.**

## Percorso 200+ → 40 → 6 → 0–3

L'input non è un ranking CSV arbitrario: la CLI ricalcola `screen()` dal bundle
locale validato, conservando gli hash delle fonti e del manifest. I punteggi
usati sono **euristiche su momentum, rischio e liquidità** già presenti nel
Blocco B. Non sono previsioni, valutazioni fondamentali complete o segnali.

1. **Copertura sufficiente:** almeno **200 strumenti in input** e
   **100 realmente ordinabili**. I candidati con dati/categorie insufficienti
   restano nelle esclusioni motivate, non assumono punteggio zero.
2. **Research pool:** massimo **40**, scelti dai punteggi esistenti con tetto
   di 10 strumenti per settore. Se non si riescono a selezionare tutti i 40
   senza violare il tetto, il sistema dichiara insufficiente la copertura.
3. **Coda di approfondimento:** massimo **6**, tutti già presenti nel pool,
   non più di 2 per settore. Un pool incompleto non viene colmato inventando
   strumenti. Il numero di candidati selezionati non è una garanzia di qualità.
4. **Finalisti provvisori:** **0 per impostazione predefinita**. Solo una
   scheda di due diligence manuale per uno strumento già nella coda di
   approfondimento lo rende candidabile a questo ultimo insieme, al massimo
   **3**. Non è una decisione d'acquisto.

Questi limiti sono **parametrizzabili** con un JSON che fornisca tutti i campi
di `DEFAULT_POLICY` e rispetti le fasce vincolanti V3.0.0:
30–60, 5–7, massimo 3. La selezione è deterministica e si può ripetere.

## Esecuzione dimostrativa offline

```bash
investresearch-b funnel \
  --bundle data/research/demo \
  --output reports/generated/block_b_funnel
```

Il demo ha **7 strumenti**, perciò il risultato corretto è
`INSUFFICIENT_RESEARCH_UNIVERSE_NO_SHORTLIST` e **nessun finalista**.

## Esecuzione con fonti autorizzate

```bash
investresearch-b funnel \
  --bundle data/private/authorized_research_bundle \
  --output data/private/research_funnel
```

La ricerca esterna resta `UNVERIFIED_NOT_TRADE_READY`, anche se i 61 prezzi
e il ranking sono formalmente validi. Per prezzi reali servono documentazione
dei diritti, identificativi ISIN, date, prezzi corretti per corporate action,
FX, dati degli altri mercati e classi di attivo; la sola provenienza dichiarata
non è una validazione indipendente. Il registro conteggia separatamente
**settori, mercati e asset class** effettivamente presenti, senza presentarli
come copertura universale.

## Due diligence e criteri di accettazione

Il file facoltativo `--diligence` contiene esattamente:
`schema_version=r007-manual-diligence-v1`, `as_of`,
`dataset_manifest_sha256`, `reviews[]`. Ogni revisione riguarda soltanto
uno degli ID del deep-dive e richiede: stato
`RESEARCH_REVIEWED_NOT_TRADE_READY`, data, tesi positiva, tesi negativa,
controtesi, limiti della valutazione e almeno un riferimento pubblico con URL
HTTPS, data di pubblicazione e SHA-256 (se disponibile). La data non può
superare `as_of`, e gli ID duplicati o assenti sono bloccanti.

**Importante:** è una *asserzione manuale*, non un fact-check automatico del
contenuto delle fonti. Il finalista conserva `trade_ready=false` e non viene
inviato ad alcun ordine. Output contenenti due diligence manuale o fonti
esterne vanno esclusivamente in una directory esterna al repository o in
`data/private/` ignorata da Git.

Il codice non legge portafogli, IBAN, saldo fiscale, costi intermediario o
minusvalenze nel repository pubblico. Qualsiasi saldo fiscale non autenticato resta un dato dichiarato nel percorso decisionale privato, distinto da un estratto certificato.

## Prove e limiti

I test sintetici ripetono il funnel su **250 record creati appositamente per
verificare il software**, derivati dalle fixture demo. **Non sono 250 emittenti
reali analizzati**. Sono coperti: ordine deterministico, controlli di
diversificazione, mancata promozione senza due diligence, date e riferimenti
futuri, hash di bundle non coerenti, filtri etici, score mancanti o NaN,
assenza di ISIN e fonte per input esterni, protezione degli export CSV da
formule e cartelle pubbliche. Evidenza: [CI 254 test](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41869669069).

**Manca per R-007 DONE:** un universo ampio reale, indipendente e multi-asset
con dati autorizzati effettivamente acquisiti; verifica della qualità e della
comparabilità dei fondamentali e delle valutazioni (R-008); funnel reale
200+→40→6→fino a 3 con fonti e revisioni eseguibili in modo riproducibile.
Non è stata usata alcuna API a pagamento e non ci sono ordini automatici.
