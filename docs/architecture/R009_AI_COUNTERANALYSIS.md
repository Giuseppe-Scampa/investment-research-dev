# R-009 / M5 — AI opzionale, gratuita dove disponibile e sotto controllo umano

**Baseline di progetto:** [V3.0.0](V3.0.0.md) (immutata), R-009.
**Stato dell'incremento:** implementazione iniziale, **PARTIAL**, non `DONE`.

## Perché e come

L'AI non genera prezzi, ordini, categorie fiscali, benchmark verificati o ranking.
È una **controanalisi non vincolante** di una ricerca *pubblica* già documentata.
Il motore deterministico B rimane utilizzabile senza AI o accesso a un modello.

Sono disponibili due modalità:

- **Ollama locale (opt-in)**: unica connessione attualmente eseguibile,
  `http://127.0.0.1:11434/api/generate`, senza proxy né redirect; timeout e
  dimensione limitati. Richiede un modello locale già installato, hardware e
  consumo energetico a carico dell'operatore. Nessuna API commerciale.
- **Importazione offline (Gemini, Groq, OpenRouter, Ollama)**: acquisisce un JSON
  già prodotto al di fuori della pipeline. Non configura né invoca quei servizi;
  **quote gratuite, termini e costi non sono ancora stati validati**. Non è
  consentito trattarli come provider integrati o come gratuiti garantiti.

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
2. Eventuali API gratuite: condizioni d'uso, quota, modalità no-billing e controllo
   dei costi prima di qualsiasi connettore remoto. Nessuna attivazione implicita.
3. Fact-check indipendente della corrispondenza citazione -> testo originale,
   con fonte autentica e prova della data di pubblicazione.
4. Revisione di sicurezza e privacy a livello dell'intera pipeline; carico di
   prova su output ambigui, prompt injection e arresto senza modello.
5. E2E cross-modulo M5/M6 con audit del risultato ma **senza sovrascrivere**
   valutazioni fiscali o dati di mercato deterministici.

La mancanza di crediti Claude **non** impedisce l'esecuzione o i test offline.
