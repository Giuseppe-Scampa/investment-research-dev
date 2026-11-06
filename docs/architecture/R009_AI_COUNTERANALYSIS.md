# R-009 / M5 — AI opzionale, gratuita dove disponibile e sotto controllo umano

**Baseline di progetto:** [V3.0.0](V3.0.0.md) (immutata), R-009.
**Stato dell'incremento:** adapter remoti Gemini/Groq/OpenRouter implementati ma **PARTIAL**, non `DONE`. Il collaudo live sui singoli account e la verifica delle condizioni di fatturazione sono separati dal codice.

## Perché e come

L'AI non genera prezzi, ordini, categorie fiscali, benchmark verificati o ranking.
È una **controanalisi non vincolante** di una ricerca *pubblica* già documentata.
Il motore deterministico B rimane utilizzabile senza AI o accesso a un modello.

Sono disponibili tre modalità:

- **Ollama locale (opt-in)**: unica connessione attualmente eseguibile,
  `http://127.0.0.1:11434/api/generate`, senza proxy né redirect; timeout e
  dimensione limitati. Richiede un modello locale già installato, hardware e
  consumo energetico a carico dell'operatore. Nessuna API commerciale.
- **Importazione offline (Gemini, Groq, OpenRouter, Ollama)**: acquisisce un JSON
  già prodotto al di fuori della pipeline senza effettuare chiamate.
- **Gemini/Groq/OpenRouter remoti (opt-in)**: una singola chiamata HTTPS a endpoint
  fisso, senza proxy/redirect/retry/fallback, con modello consentito e token
  massimi limitati. Richiede **tre flag espliciti**: `--invoke-free-remote`,
  `--acknowledge-free-tier`, `--acknowledge-public-only`. Le chiavi
  provengono solo dalle variabili ambiente. L'applicazione **non può
  controllare lo stato di fatturazione** dell'account: serve verifica umana.

L'utente deve invocare il comando e attestare che domanda e *excerpt* contengano
esclusivamente dati societari pubblici. Il gateway **rifiuta campi privati** e
riconosce alcune stringhe a rischio (email, IBAN), ma nessun filtro testuale è
sufficiente a certificare l'assenza di dati personali: i documenti bancari e lo
zainetto fiscale **non vanno mai passati all'AI**.

## Schema del public input

Esempio interamente inventato: `config/ai_public_review_example.json`.
Campi ammessi esatti:
`schema_version=r009-public-research-v1`,
`data_scope=PUBLIC_ISSUER_RESEARCH_ONLY_NO_PERSONAL_DATA`,
`as_of`, `question`, `sources[]`.
Ogni fonte: `source_id` unico, `url` HTTPS pubblico, `published_date`
non posteriore ad `as_of`, `excerpt` limitato a 1500 caratteri,
`sha256` opzionale (64 caratteri o null).

Il checksum comunicato **non** è confrontato con il documento reale.
I source_id impediscono citazioni verso fonti inesistenti nel registro,
ma **non verificano che una fonte sostenga davvero l'affermazione**.

## Schema delle risposte esterne

Il file `--response-json` deve contenere solamente:

```json
{
  "summary": "Short critical view of the public evidence",
  "counterarguments": [{"claim": "Reasoned objection", "source_ids": ["SRC1"]}],
  "uncertainties": ["A limitation not resolved by the supplied evidence"]
}
```

Un riferimento a un ID assente, una risposta non JSON o un campo aggiuntivo
bloccano la produzione del report. I testi del modello sono **non verificati**.

## Esecuzione offline (nessuna API)

```bash
investresearch-b ai-countercheck \
  --spec config/ai_public_review_example.json \
  --provider gemini --model imported-response \
  --response-json config/ai_public_response_example.json \
  --acknowledge-public-only \
  --output data/private/r009-imported-demo
```

Questa procedura **non chiama Gemini**. L'indicazione `gemini` è solo la
provenienza dichiarata dall'operatore del file importato; il motore non la
autentica.

## Esecuzione locale esplicita con Ollama

Con Ollama già disponibile sulla propria macchina e un modello già installato:

```bash
investresearch-b ai-countercheck \
  --spec data/private/public_research_only.json \
  --provider ollama-local --model MODELLO_LOCALE_ESISTENTE \
  --invoke-local-ollama --acknowledge-public-only \
  --output data/private/r009-local-output
```

Nessun fallback a provider esterni. Il servizio locale non è raggiunto se
mancano le opzioni di consenso. Non eseguire questo comando in GitHub Actions.


## API remote opzionali — contratto operativo novembre 2026

- Secret esatti: `GEMINI_API_KEY`, `GROQ_API_KEY`,
  `OPENROUTER_API_KEY`. Non includere chiavi in commit, prompt, issue o log.
- Gemini: `gemini-2.5-flash-lite` o `gemini-2.5-flash` **solo quando il
  progetto è effettivamente sul Free tier**. L'API può essere a pagamento
  sullo stesso modello quando il progetto ha billing attivato.
- Groq: `openai/gpt-oss-20b` o `openai/gpt-oss-120b` **solo con piano
  Free verificato**. `llama-3.3-70b-versatile` è **escluso**: dismesso
  sul piano gratuito dal 16 agosto 2026.
- OpenRouter: consentito soltanto l'ID di **un modello specifico**
  terminante in `:free`, ad esempio il modello attualmente elencato
  `google/gemma-4-26b-a4b-it:free`. Il router dinamico `openrouter/free`,
  i suffissi `:online` / `:floor` e gli ID a pagamento sono bloccati.
  Il cap chiave pari a 0,01 USD non è una garanzia di costo zero.

Esempio locale, **soltanto documenti societari pubblici** (non posizioni,
importi, fiscale, portfolio):

```bash
investresearch-b ai-countercheck \
  --spec config/ai_public_review_example.json \
  --provider groq --model openai/gpt-oss-20b \
  --invoke-free-remote --acknowledge-free-tier --acknowledge-public-only \
  --output data/private/r009-groq-public-demo
```

Per utilizzare i secret già configurati nel repository pubblico è stato
aggiunto `.github/workflows/r009-manual-free-ai.yml`. **Il workflow_dispatch
diventa disponibile dalla UI GitHub soltanto dopo la presenza del workflow
sul ramo predefinito**; mentre la PR è aperta, il solo commit sul feature
branch non abilita necessariamente il pulsante Run workflow.
Una volta approvato e distribuito, il workflow esegue su conferma umana **una**
richiesta contro una fixture 100% sintetica e può caricare soltanto i suoi
risultati fittizi nel repository pubblico. Per vere analisi riservate usare
ambiente privato, mai Actions/artifact pubblici.

La sola presenza dei tre secret GitHub **non prova la corretta configurazione
del piano**, né esegue test live. Risposte remote sono marcate con
`execution=OPT_IN_FREE_TIER_REMOTE` e
`api_billing_status=FREE_TIER_OPERATOR_ACKNOWLEDGED_BILLING_NOT_ATTESTED`.
Confronti fra provider restano non verificati, e non autorizzano prezzi,
classificazione fiscale, ranking o ordini.

Fonti per riconfermare condizioni e modelli:
- https://ai.google.dev/gemini-api/docs/pricing
- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/deprecations
- https://openrouter.ai/collections/free-models

## Output e privacy

Solo `AI_COUNTERANALYSIS.json` e `.md`, scritti in un percorso locale
`data/private/` ignorato da Git oppure esterno al repository. Rifiuta
l'overwrite per evitare la perdita di analisi già revisionate.
Il report include:
- hash di spec e risposta (integrità/riproducibilità, non autenticazione);
- fonte e data dichiarata, ID delle citazioni;
- avviso `AI_UNVERIFIED_COUNTERANALYSIS_HUMAN_REVIEW_REQUIRED`;
- `rank_or_tax_authorization=false`, sempre.

I modelli possono sbagliare, inventare spiegazioni e interpretare erroneamente
fonti pubbliche: **nessun output AI può promuovere una ricerca a trading-ready**.

## Criteri ancora aperti per R-009 DONE

1. Verifica effettiva locale Ollama su almeno un modello autorizzato con evidenza
   riproducibile senza contenuto privato o download non approvato.
2. Collaudo live sui tre provider soltanto dopo attestazione esterna di Free
   tier/account, senza fatturazione, quote e condizioni privacy. Adapter e
   test mock non equivalgono a un provider live verificato.
3. Fact-check indipendente della corrispondenza citazione -> testo originale,
   con fonte autentica e prova della data di pubblicazione.
4. Revisione di sicurezza e privacy a livello dell'intera pipeline; carico di
   prova su output ambigui, prompt injection e arresto senza modello.
5. E2E cross-modulo M5/M6 con audit del risultato ma **senza sovrascrivere**
   valutazioni fiscali o dati di mercato deterministici.

La mancanza di crediti Claude **non** impedisce l'esecuzione o i test offline.
