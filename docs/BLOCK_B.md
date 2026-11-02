# Blocco B — acquisizione, provenance e screening quantitativo (M3 + M4)

**Stato:** implementazione e test offline; la compatibilità effettiva con i provider
esterni NON è stata verificata con chiamate live in questo ambiente. Dati inclusi
nel repository: **100% inventati e marcati sintetici**.

## Primi comandi, senza account e senza rete

```bash
python -m pip install -e '.[test]'
pytest -q
investresearch-b screen --bundle data/research/demo --output reports/generated/block_b
# Ricalcola, se necessario, il dataset deterministico:
PYTHONPATH=src python -m investresearch.demo_dataset
```

Output: `BLOCK_B_SCREENING.json`, `.csv`, `.md` e `block_b_dashboard.html`.
La demo comprende sette strumenti fittizi, un USD, un fondo, un petrolifero
escluso, un titolo con storico insufficiente, fondamentali annuali inventati,
FX inventati ed eventi inventati. **Nessun titolo reale viene classificato**
con la demo. Si rifiutano automaticamente dataset con hash difformi o percorsi
che escono dal bundle.

## Provider e vincoli gratuiti

| Fonte | Uso | Stato | Condizioni |
|---|---|---|---|
| **SEC EDGAR** `data.sec.gov` | Annual 10-K companyfacts XBRL, USD | Ufficiale, senza API key | Contatto identificativo reale per User-Agent, limiti SEC, assenza di CORS |
| **BCE** `ecb.europa.eu` | USD per EUR, riferimenti FX storici | Ufficiale, senza API key | Riferimento giornaliero, NON cambio eseguibile o fiscale del broker |
| **Stooq** CSV | OHLCV storici per screening | **Terza parte non verificata** | Opt-in, chiave gratuita quando richiesta, termini di utilizzo e possibile limite personale/non commerciale |

Documentazione primaria: [SEC XBRL APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[SEC fair access](https://www.sec.gov/about/developer-resources),
[cambi di riferimento BCE](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).
**Non ridistribuire dataset Stooq senza autorizzazione prevista dalla licenza.**
L'acquisizione di dati pubblici non equivale all'acquisizione di dati di livello
professionale o alla disponibilità di prezzi eseguibili.

### Acquisizione esplicita

La CI **non esegue richieste di rete**. I seguenti comandi sono facoltativi:

```bash
# SEC impone contatto valido nel User-Agent. Non inserirlo nel repository.
export SEC_RESEARCH_CONTACT='indirizzo-contatto-reale@example.org'
investresearch-b collect --provider SEC_COMPANYFACTS --identifier 0000320193

# BCE / cambi USD per EUR
investresearch-b collect --provider ECB_EUR_FX

# Stooq solo se l'utente ha una chiave gratuita e accetta i termini:
export STOOQ_FREE_KEY='CHIAVE_FREE_PRIVATA'
investresearch-b collect --provider STOOQ_EOD_UNVERIFIED \
  --identifier aapl.us --acknowledge-stooq-terms
```

Il primo esempio di contatto è un **segnaposto**, da sostituire con un contatto
reale autorizzato. Non abilitiamo automaticamente provider alternativi,
retry costosi, scraping con bypass dei blocchi o upgrade a pagamento. I codici
403/429 sono errori espliciti. Cache `.cache/research/`: ogni payload riceve un
hash SHA-256 e un file metadati con URL redatto, timestamp e tipo di fonte.
La cache non è nel repository.

### Importazione locale di un bundle reale

1. Recuperare i file raw dai provider con `collect` o manualmente, rispettando
   le licenze. Compilare uno spec JSON nello stile di
   `config/research_import_example.json` con `as_of`, `mode`, `assets`, `fx_source`
   ed eventualmente `events_source`.
2. Inserire nei campi `path` i percorsi locali dei blob/csv effettivi, e nei
   campi `sha256` gli hash dichiarati dal downloader. Indicare l'URL HTTPS del
   provider appropriato; non dichiarare SEC o BCE per un file di altra origine.
3. Eseguire:

```bash
investresearch-b build --spec data/private/import_spec.json \
  --output data/private/research_bundle
investresearch-b screen --bundle data/private/research_bundle \
  --output reports/generated/block_b
```

**La CLI non importa automaticamente il patrimonio reale e non cerca prezzi
alternativi in caso di lacune.** Un file provvisto di fonte non è per questo
considerato una quotazione eseguibile o un dato verificato da un exchange.
I file in `data/private/` e `.cache/` sono esclusi da Git.

#### Schema delle evidenze

Lo spec di importazione contiene `mode=EXTERNAL_RESEARCH_SOURCES_NOT_EXECUTABLE`,
`as_of=YYYY-MM-DD`, `assets[]` con `id`, `name`, `venue` (codici MIC supportati),
`currency` (EUR/USD), `asset_type`, `isin` facoltativo ma verificato quando
presente, `sector`, `oil_exposure`, `index_memberships` e `prices_source`.
La fonte prezzo normalizza Stooq `Date,Open,High,Low,Close,Volume` come
`date,close,volume`. Il prezzo non è dichiarato *adjusted* o total-return.
`fundamentals_source` per SEC richiede `sec_cik` che corrisponda al campo CIK
nel JSON e nell'URL `CIK##########.json`.
Per ogni riga vengono registrati `raw_sha256`, `sha256` normalizzato, fonte
ed eventualmente timestamp di acquisizione. L'output CSV normalizzato è
sempre accompagnato da un manifest hashable.

**Nota sulla portabilità:** il bundle contiene gli hash originali ma non
ridistribuisce necessariamente i raw snapshot dei provider. Per un audit completo
conservare i blob nella cache e non sovrascriverli. Il manifest garantisce
integrità dei file normalizzati, non autenticità assoluta della fonte.

## Fondamentali, dati point-in-time e scoring

La lettura delle `companyfacts` SEC estrae solo **ricavi e utile netto annuale**
con periodo coerente, denominazione USD e filing presentato entro `as_of`.
Restatement depositati dopo la data non possono entrare nel dataset.
I valori sono **contabili storici**, non una misura di convenienza del titolo.
L'estrazione automatica non sostituisce le note integrative e può essere
inadeguata per banche, assicurazioni, IFRS non ricondotti a US GAAP o aziende
con concetti XBRL non standard.

Il ranking del dataset completo richiede almeno 61 sedute storiche allineate,
quotazioni entro la tolleranza di freschezza, nessun blocco settoriale e,
per prezzi USD, FX BCE su osservazioni della **stessa data**. Non si sostituisce
l'ultimo cambio mancante con quello di un'altra seduta. Non si confrontano
rendimenti nominali USD direttamente con rendimenti EUR.

### Scoring esplicito e non predittivo

| Fattore | Peso | Trasformazione |
|---|---:|---|
| Momentum 20 osservazioni allineate | 30% | Valore normalizzato tra -25% e +25% |
| Momentum 60 osservazioni | 20% | Tra -40% e +40% |
| Volatilità annualizzata su 20 rendimenti | 20% | Più bassa = punteggio maggiore, intervallo 10%-100% |
| Drawdown delle ultime 61 osservazioni | 15% | Tra -50% e 0% |
| Turnover quotidiano medio in EUR | 15% | Log10 dei volumi monetari da €10k a €100m |

Punteggi in scala 0–100. **Limiti e pesi sono euristiche dichiarate, non
validati come modelli predittivi.** Le aziende con dati SEC ricavi/utile
possono avere un secondo punteggio illustrativo composto da 85% score mercato
e 15% net margin annuale normalizzato; questa seconda graduatoria è distinta
dalla prima e non penalizza ETF o aziende senza fondamentali disponibili.
Una correlazione fra questi punteggi e performance future non è stata testata.

Gli eventi macro/earnings/policy/geopolitici entrano tramite registro
**documentato da fonte, data evento e data di pubblicazione**. Se la data di
pubblicazione è futura rispetto ad `as_of`, l'evento viene escluso. Gli eventi
non incidono sui punteggi senza una successiva metodologia quantitativa
verificata. Nella demo sono fittizi.

Le previsioni, la negoziabilità, la natura fiscale dell'ISIN, le esposizioni
indirette e le raccomandazioni restano esplicitamente **fuori dal grado di
validazione di Blocco B**. Non viene chiamata nessuna API a pagamento.

## Stato di completamento / prossimi controlli

**Implementati:** manifest e hash, parser e cache, acquisizione manuale SEC/BCE/Stooq,
normalizzazione point-in-time, scoring deterministico con valuta EUR, overlay
fondamentale, eventi source-dated, CSV/JSON/Markdown/dashboard, test offline.

**Da confermare prima dell'uso di mercato:** download reale e termini dei
provider, mappatura di un ampio universo di ISIN e CIK, corporate actions,
metodologia quantitativa sui diversi settori, quotazioni ufficiali, qualità
storica e backtest out-of-sample. Nessuna shortlist operativa è prodotta.

## Secondo incremento — discovery reale e qualità avanzata

### Universi SEC senza ranking fittizi

La nuova fonte ufficiale **SEC_TICKERS** consente di scaricare il file corrente
`https://www.sec.gov/files/company_tickers_exchange.json` con un contatto
esplicito SEC nel `User-Agent`. La stessa cache SHA-256 conserva raw e metadati.

```bash
export SEC_RESEARCH_CONTACT='tuo-contatto-effettivo@example.org' # sostituisci
investresearch-b collect --provider SEC_TICKERS
# Leggi i due path .bin e .json stampati/salvati in .cache/research/SEC_TICKERS/SEC_CATALOG/
investresearch-b universe \
  --raw .cache/research/SEC_TICKERS/SEC_CATALOG/<sha256>.bin \
  --metadata .cache/research/SEC_TICKERS/SEC_CATALOG/<sha256>.json \
  --as-of 2026-11-02 --limit 1000 --output data/private/sec-candidates
```

**Importante:** lo snapshot SEC è una mappa *corrente* ticker–CIK–exchange,
non un universo storico privo di survivorship bias, non un classificatore
settoriale e non una lista di titoli negoziabili. L'importatore rifiuta snapshot
acquisiti **dopo** il `as_of`, richiede hash e URL ufficiale e salva solo un
catalogo *CANDIDATE_ONLY* US (NYSE/Nasdaq riconosciuti). Non attribuisce
automaticamente ISIN, esposizione etica, fondamentali o quotazioni. Per Europa,
Asia e altre classi di attivo servono cataloghi ulteriori e mapping documentato.

### Gate prima di attribuire un punteggio

- Le 61 osservazioni devono coincidere con **61 sedute consecutive** del
  mercato indicato, non semplicemente 61 righe. Buchi, sedute fittizie e
  calendari non supportati impediscono il punteggio.
- Movimenti giornalieri assoluti oltre il **60%** sono uno *stop di revisione*
  (possibile split, prezzo corrotto o evento reale): non vengono corretti
  automaticamente, ma richiedono corporate action documentate. La soglia è
  cautelativa e NON una regola universale di trading.
- Con fonti esterne la data di raccolta dei **prezzi e cambi** deve essere
  documentata e non successiva al `as_of`; altrimenti il ranking è sospeso.
  Mancanza di classificazione settoriale/esposizione petrolifera = non classificabile.
- I fondamentali SEC devono associare ricavi e utile dello stesso periodo e,
  se presenti, della **medesima accession EDGAR**; con accession assente,
  data di acquisizione mancante o successiva ad `as_of`, viene sospeso **solo
  il ranking fondamentale**, non il punteggio di mercato eventualmente valido.
- L'algoritmo resta valido unicamente per i calendari 2026 documentati;
  l'estensione a più anni e la validazione degli aggiustamenti per dividendi,
  split e ticker changes sono ancora attività aperte.

### Verifica live indipendente

Il job GitHub Actions `live_ecb_smoke`, in esecuzione sulle PR, effettua **una**
chiamata HTTPS alla BCE, verifica l'hash e prova il parser CSV su dati reali.
È *best effort*: l'insuccesso per rete/429 non rende rossa la CI offline,
ma i log devono riportarne esplicitamente l'esito. Le API SEC (contatto reale)
e Stooq (chiave gratuita e termini) non vengono richiamate automaticamente.
Non interpretare la CI verde come prova che SEC/Stooq siano stati interrogati.

### Controllo live BCE: anomalia identificata e mitigazione

Il primo smoke su GitHub ha mostrato una risposta CSV BCE formalmente
leggibile ma con ultima osservazione risalente al 2010: **non valida** per
una ricerca 2026. L'acquisizione BCE usa ora l'endpoint ufficiale XML
`https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml`, preservando
solo la compatibilità di lettura con vecchie cache CSV. Il collector applica
un controllo di freschezza (ultima osservazione non oltre 14 giorni prima
 della data corrente) e rifiuta esplicitamente feed formalmente corretti ma
 obsoleti. Lo smoke live deve mostrare un'ultima osservazione recente e non
 solo la validità del parsing. Nessun fallback nascosto o servizio a pagamento.
