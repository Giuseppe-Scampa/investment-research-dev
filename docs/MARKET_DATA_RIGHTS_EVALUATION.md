# Blocco B · fonti prezzi storici: valutazione diritti e percorso di integrazione

**Data valutazione: 2 novembre 2026. Non è stata identificata o certificata un'API gratuita e generalista per la copertura operativa dell'intero universo.** Un mercato che pubblica gratuitamente dati ritardati non concede automaticamente uno storico OHLCV completo, né l'utilizzo sistematico o commerciale in un motore di ranking.

| Fonte | Evidenza pubblica | Utilizzo previsto in M4 | Decisione |
| --- | --- | --- | --- |
| Yahoo Finance / yfinance | Adapter tecnico già testato, ma termini da verificare e nessun titolo di licenza commerciale acquisito | Ricerca **locale, esplicita, non redistribuita** | `RESEARCH_UNVERIFIED_LOCAL_ONLY`; nessun report pubblico con serie Yahoo |
| Euronext / Borsa Italiana | [Policy dati Euronext](https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies): delayed data gratuita per uso interno; categorie display, non-display e redistribuzione distinte | Possibile copertura venue ufficiale, non con semplice copia di pagine web | Richiedere conferma di **licenza per download storico e calcolo automatico** e canale di distribuzione/CSV/API prima di sviluppare un adapter |
| Euronext NextHistory | [Prodotto EOD](https://www.euronext.com/en/products-services/nexthistory): OHLC, volume, dividendi e adjustment factor | Candidato tecnico ideale per qualità, ma condizioni economiche/accesso da determinare | Non attivare finché costi e diritti non sono noti |
| Cboe Europe | [Data Policy agosto 2026](https://cdn.cboe.com/resources/participant_resources/Cboe_Europe_Data_Policy_August_2026.pdf): EOD distribution senza fee/accordo; regole diverse per dati delayed/historical | Possibile secondario su sedi Cboe; la policy EOD non dimostra disponibilità di API storica gratuita né equivalenza con i prezzi della sede primaria | Verificare feed tecnico, instrument mapping e diritto specifico d'uso; **non selezionato** |
| Cboe MiFID public downloads | [Disclaimer Cboe](https://www.cboe.com/europe/equities/trade_data/): CSV ritardati gratuitamente, con esclusione di utilizzi commerciali | Non adatto come feed generalista di chiusure aggiustate | Non fare download automatizzato commerciale |
| CSV fornito in modo autorizzato dall'utente | Fonte, SHA-256 e `LOCAL_RESEARCH_RIGHTS_ASSERTED_NOT_VERIFIED` | Importatore M3 già operativo con score soltanto `UNVERIFIED_NOT_TRADE_READY` | Consentito **solo locale** e con origine/diritti dichiarati, mai certificati dal motore |

## Contratto minimo prima di abilitare un provider reale

1. **Diritti:** termini contrattuali e permessi che coprano download sistematico, conservazione, analisi non-display, eventuali indicatori derivati e pubblicazione di output; definire chi può accedere ai risultati.
2. **Identità degli strumenti:** ISIN, MIC della sede effettiva, valuta di negoziazione, ticker canonico, cambi ticker/corporate actions, tipo strumento e negoziabilità italiana.
3. **Storico:** 61 o più sedute consecutive (preferibilmente 250–500), fuso orario, orari e calendario, nessuna ricostruzione silenziosa delle sedute mancanti; quotazioni con origine documentata e timestamp.
4. **Economic returns:** dividendi cash, distribuzioni, split, reverse split, fusioni, diritti e loro fattori/tempi; distinguere serie raw, split-adjusted e total return. Un rendimento basato sul solo `Close` **non** rappresenta total return.
5. **Seconda fonte per finalisti:** confronto prezzi e corporate action con sito dell'emittente, sede di quotazione o broker, segnalando divergenze invece di risolverle automaticamente.
6. **Operatività distinta:** bid/ask, costi bancari effettivi, fiscalità ISIN e liquidità disponibile al momento dell'ordine non derivano da un prezzo EOD.

**Soglie di avanzamento:** `UNVERIFIED_LOCAL` può alimentare solo schermate di ricerca privata; `LICENSED_SOURCE_VALIDATED` richiede conferma documentale diritti, mapping, correzioni corporate action e controlli campione. L'importatore attuale non consente una promozione automatica da uno stato all'altro. L'intera PR #2 resta in draft finché il motore non dispone di una fonte reale adeguata e delle verifiche con i dati europei ufficiali.
