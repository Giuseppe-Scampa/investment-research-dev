# R-004 / R-006 / R-009 — utenze, fonti e dipendenze per V3.0.0

**Verificato su documentazione ufficiale il 4 novembre 2026.**
Questo file distingue **creazione dell'account**, **disponibilità dell'endpoint**,
**diritti di utilizzo dei dati**, **qualità analitica** e **diritti di
redistribuzione**. Il successo di una API non equivale a nessuna delle ultime
tre condizioni.

## Account da usare nelle varie fasi

| Fase | Servizio | Creare utenza? | Stato in codice | Blocco prima della produzione |
|---|---|---|---|---|
| Ora (M3/M4) | SEC EDGAR/companyfacts/ticker catalog | **No**; fornire User-Agent con contatto | SEC pilot già presente; non sostituisce anagrafiche ISIN/venue | Usare limiti SEC, verificare società e punto nel tempo |
| Ora (M3) | BCE riferimento EUR FX | **No** | Parser + pilot esistenti | FX fixing ≠ cambio contemporaneo delle chiusure USA |
| Pilot immediato M3 | Alpha Vantage | **Sì: chiave Free**; nessuna carta/piano a pagamento | **Nuovo** `alpha-pilot` opt-in locale | Solo raw DAILY compact 100 barre; niente split/dividendi rettificati, venue/ISIN/licenza non certificati |
| R-006/M4 dopo pilot | Euronext e altre fonti europee | **Non ancora** | Registry ESEF e manual OHLCV già presenti | Verificare separatamente licenza, storici, corporate actions e non-display |
| R-009/M5 | Ollama locale | **No account cloud** | Unico gateway effettivamente chiamabile, in loopback, esplicito | Installazione/modello locale, benchmarking, citazioni ancora non verificate |
| R-009/M5 | Gemini API/AI Studio | **Più avanti**, account/progetto Free | Attualmente soltanto importazione di risposta offline | Quote per modello, privacy dei prompt, condizioni EEA e no billing |
| R-009/M5 | GroqCloud | **Più avanti**, account/progetto Free | Attualmente soltanto importazione di risposta offline | Rate limit effettivo della propria organizzazione, zero billing |
| R-009/M5 | OpenRouter | **Solo se utile**, account Free | Attualmente soltanto importazione di risposta offline | Modelli esplicitamente `:free`, limiti, retention dei prompt |
| R-009/M5 | Cloudflare Workers AI | **Solo se utile**, usare un account Free esistente | Nessuna integrazione necessaria ora | 10.000 Neurons/die free; alcuni modelli richiedono pagamento |
| Non necessario per MVP | Oracle Cloud | **No** | Non è dipendenza di V3.0.0 | Evitare nuove cloud gratuite complesse prive di utilità verificata |

Non trasformare la piattaforma AI in dipendenza della pipeline deterministicа:
l'algoritmo di discovery, il preflight fiscale e i report devono funzionare
offline senza modelli e senza credenziali.

## Limiti ufficiali da verificare quando si crea l'account

- SEC: [documentazione accesso](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
  e [User-Agent](https://www.sec.gov/about/webmaster-frequently-asked-questions);
  limite generale SEC 10 request/s, da non saturare; collegare solo il
  `SEC_RESEARCH_CONTACT` segreto, non in commit/log pubblici.
- Alpha Vantage: [documentazione TIME_SERIES_DAILY](https://www.alphavantage.co/documentation/)
  e [supporto](https://www.alphavantage.co/support/).
  Il livello standard gratuito dichiara 25 richieste al giorno. La serie
  `TIME_SERIES_DAILY` in `compact` contiene le ultime 100 osservazioni
  **raw**; `TIME_SERIES_DAILY_ADJUSTED` è indicata Premium.
  La disponibilità della chiave **non** certifica il diritto a fare ranking
  massivo, usare derivati o redistribuire serie.
- Euronext: [politiche dati](https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies),
  [NextHistory](https://www.euronext.com/en/products-services/nexthistory).
  Display delayed accesso individuale ≠ utilizzo non-display automatico.
- Gemini: [Free Tier, billing](https://ai.google.dev/gemini-api/docs/billing)
  e [pricing](https://ai.google.dev/gemini-api/docs/pricing).
  Il livello Free è disponibile in molti Paesi UE, può usare contenuti per
  il miglioramento dei prodotti e richiede limiti per modello. Il codice non
  deve abilitare billing o modelli a pagamento.
- Groq: [billing Free](https://console.groq.com/docs/billing-faqs) e
  [rate limits](https://console.groq.com/docs/rate-limits);
  la soglia applicabile è quella della console dell'account/progetto.
- OpenRouter: [pricing e free requests](https://openrouter.ai/pricing);
  i modelli `:free` senza acquisti di crediti hanno limite dichiarato
  50 richieste/giorno; non inviare dati personali.
- Cloudflare: [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
  e [limitazioni modelli Free 2026](https://developers.cloudflare.com/changelog/post/2026-07-28-models-require-workers-paid/).

## Nuovo pilot Alpha Vantage (senza imporre l'utenza alla CI)

Il comando `investresearch-b alpha-pilot` è una **diagnostica manuale**.
Richiede la chiave **solo** nella variabile d'ambiente
`ALPHAVANTAGE_API_KEY` impostata localmente tramite un sistema di gestione
segreti. Non accetta chiavi nel codice, in un file configurazione versionato
o negli argomenti da terminale. Non pubblicare output nella PR o in Actions.

Dopo avere verificato i termini, autorizzato l'uso locale ed
esplicitamente selezionato un mercato `MIC` (non dedotto dal ticker):

```bash
# Impostare ALPHAVANTAGE_API_KEY nel proprio secret store locale PRIMA.
# Il comando effettua una sola richiesta per un solo simbolo, senza retry:
investresearch-b alpha-pilot \
  --symbol IBM --venue XNYS \
  --live-confirm --acknowledge-source-terms \
  --output data/private/alpha-pilot-IBM
```

L'output locale contiene solo `ALPHA_DAILY_UNVERIFIED.csv` e
`ALPHA_PILOT_METADATA.json`, con hash, data di acquisizione UTC, conteggio
delle sedute, fonte **senza API key** e limitazioni. Il programma:

- accetta soltanto l'endpoint ufficiale `TIME_SERIES_DAILY` con
  `outputsize=compact`, formato JSON, una singola richiesta HTTPS;
- non esegue fallback a endpoint premium o provider alternativi;
- rifiuta risposte di errore/rate-limit, JSON non valido, mismatch simbolo,
  date future, dati OHLCV incoerenti e percorsi di output pubblici;
- **non** importa il risultato nel bundle di ranking e non attribuisce
  ISIN, adjusted close, calendari, dividendi o licenze;
- **non** prova automaticamente che il prezzo sia tradable o utilizzabile
  per scopi commerciali. Controllare i termini prima della raccolta.

La chiave va **creata solo prima del primo test reale**: codice e test
sintetici non ne hanno bisogno.

## Roadmap di dipendenza effettiva

1. **M3 R-004/R-005:** eseguire un pilot autorizzato su pochi simboli,
   verificare 61+ sedute, coerenza con un sito di borsa e corporate actions,
   ottenere un riscontro documentato sul diritto di analisi locale.
2. **M4 R-006:** affiancare discovery SEC e europei con mappatura
   `issuer → ISIN → listing/MIC → prezzo/valuta → fonte/diritti`. Nessun
   record viene promosso senza identificativi e qualità verificati.
3. **M4 R-007/R-008:** alimentare il funnel 200+→40→6→0–3 con dati realmente
   indipendenti, valuation, fattori e controtesi, non solo i 250 record
   sintetici dei test.
4. **M6 R-010:** costruire il contratto di trasferimento dell'evidenza
   `B→A`, senza saldo bancario in repository pubblico.
5. **M2 Decision 2026:** per la sola ricerca usare **solo in ambiente privato un saldo fiscale fornito dall'operatore**,
   marcato `USER_CONFIRMED_NOT_BROKER_VERIFIED` quando non certificato dall'intermediario;
   non serve ricostruire ogni operazione passata per confrontare A/B/C.
   La capienza e il regime dell'intermediario vanno verificati
   prima di tradare.

**Non sono prerequisiti:** nuovi conti cloud, subscription Euronext,
Ollama sul cloud, upgrade di Gemini/Groq, conto bancario collegato al pubblico.
