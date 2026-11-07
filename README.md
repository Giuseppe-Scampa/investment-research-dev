# Investment Research Engine — public technical demonstration

> **Architettura ufficiale condivisa:** [indice e versione V3.0.0](docs/architecture/README.md) · [roadmap M1–M6](docs/architecture/ROADMAP.md) · [assessment Claude/Gemini](docs/architecture/ASSESSMENT_PROMPTS.md). Il perimetro permanente del Research Engine resta distinto dal percorso fiscale personale 2026. Ogni revisione architetturale segue SemVer + ADR.

This is a **synthetic, public technical example** of an independent financial research engine with a modular Italian taxation and investment-cost simulation. It is provided for review and development, not for personal financial advice or trade signals.

**All portfolio capital, loss carryforwards, broker information, commission schedules and positions are fictitious.** They are test inputs, not a person's actual financial data. Prices in `data/snapshots/` are historical public-source research references, **not executable bid/ask quotes**.

## Scope

- M1: strict data quality, duplicate/identity validation, exchange-session awareness, staged readiness, numerical validation.
- M2: versioned 2026 illustrative tax-category registry, loss-offset simulation, costs, existing holdings scenario, alternatives A/B/C, local decision ledger.
- Free/offline only. **No OpenAI API / paid AI integration in this public release.** Future AI work is independent.
- No automated trading, broker API or live advice. Tax rules and specific ISIN classifications require external verification before real decisions.

## Run offline

```bash
python -m pip install -e '.[test]'
pytest -q
investresearch report
python -m investresearch.dashboard
```

To review the A/B/C simulated portfolio, see `reports/generated/` after running the command. You can use a *local, never committed* input file with `investresearch report --case data/private/portfolio_private.json`. Do **not** upload personal case files to a public GitHub repository or Actions.

## Free GitHub Actions

Run **Actions → Manual offline analysis (no paid API)** or CI. Actions only use the included **synthetic** settings and fixtures. The optional `refresh` mode uses yfinance and labels histories as unverified.

## Docs

- `docs/INPUT_SCHEMA.md`: positions and portfolio case format.
- `docs/FISCAL_SOURCES.md`: public source references, provisional tax assumptions and limitations.
- `docs/BLOCK_A_ASSESSMENT.md`: implementation audit and remaining risks.
- `docs/PUBLIC_RELEASE_CHECKLIST.md`: publication checks and clean-history rationale.

## Publication boundary

This public development repository contains **synthetic cases only**, no historical commits from the private project, no private trading records and no billable AI workflow. Never import private case files or raw provider records with restricted redistribution rights into this public history.

## Blocco B — fonti gratuite e screening verificabile (sviluppo)

Il **Blocco B** aggiunge un percorso di ricerca separato da quello fiscale, con
bundle locali verificati SHA-256, punteggi storici deterministici e un overlay
fondamentale per le azioni. Per provare l'intera pipeline **senza rete**:

```bash
investresearch-b screen --bundle data/research/demo --output reports/generated/block_b
# In alternativa: python -m investresearch.research_cli screen
```

Il dataset incluso contiene **esclusivamente dati sintetici**: i punteggi NON
sono classifiche reali, previsioni né raccomandazioni. L'acquisizione live è
**solo su comando esplicito** con limiti conservativi; nessuna API a pagamento.
La provenienza, i requisiti dei provider e gli esempi d'importazione sono in
[`docs/BLOCK_B.md`](docs/BLOCK_B.md). Nessun ordine viene trasmesso.

### Blocco B — catalogo società SEC e controlli data quality

Nel branch di sviluppo è disponibile il catalogo SEC per costruire fino a
10.000 candidati *non classificati*, `investresearch-b universe`, a partire da
un download **esplicito** dell'elenco ufficiale SEC. È una discovery US-only,
non una shortlist finanziaria. La graduatoria richiede storici completi,
provenienza verificabile, data di acquisizione coerente con `as_of` e controlli
sui possibili split. Vedi [docs/BLOCK_B.md](docs/BLOCK_B.md).


### SEC e dati storici Yahoo (in opt-in)

- La SEC usa il secret GitHub `SEC_RESEARCH_CONTACT` esclusivamente nel workflow **Manual source probe**.
  Le API EDGAR non richiedono un account, un token o un piano a pagamento.
- Stooq non viene più utilizzato. `YFINANCE_EOD_UNVERIFIED` è un adattatore opzionale
  a Yahoo via yfinance **senza API key**, per ricerca personale secondo i termini Yahoo;
  nessun download live avviene in automatico durante i test o nelle PR.
- Il workflow è visibile nell'interfaccia Actions dopo l'inclusione in `main`.
  Nessuno snapshot SEC/Yahoo viene pubblicato come artefatto pubblico.
- Vedi [`docs/BLOCK_B.md`](docs/BLOCK_B.md) per istruzioni e limiti di licenza.

### Blocco B — prima copertura SEC su dati reali

`investresearch-b sec-pilot --live-confirm --symbols AAPL,MSFT,NVDA,AMZN`
uses the official SEC ticker catalog and annual US-GAAP companyfacts through
bounded, explicit requests. It requires `SEC_RESEARCH_CONTACT` in the process
environment (not in the repository) and produces **issuer coverage and net
margin only**, **not** a real investment ranking. See `docs/BLOCK_B.md` for
security, scope and local-only report instructions.

### SEC — bounded expanded annual research cohort (new milestone)

For an explicit, limited SEC evidence exercise (not a market ranking), use
`investresearch-b sec-pilot --live-confirm --cohort config/sec_cohort_example.json`.
The 18-ticker sample uses only public SEC records; comparable revenue growth is
reported **only for same-accession prior-year annual observations**. It never
inventories ISINs, prices or sector labels. See [SEC cohort methods](docs/SEC_COHORT.md).

### EU annual disclosures and locally authorized price input (offline)

Block B now includes an **EU ESEF/XHTML/PDF document integrity register** and an **explicit, local-only market-price CSV import**. These add coverage paths for non-US issuers without claiming automatic IFRS extraction or unrestricted market-data licensing. The program verifies checksums and as-of dates; source authenticity, accounting facts and provider rights still require independent review.

```bash
# Copy config/eu_filings_example.json into data/private/ and fill real document metadata.
investresearch-b eu-filings --spec data/private/eu-filings.json --output reports/generated/private-eu-evidence
# A separate config/manual_prices_example.json demonstrates user-authorized local OHLCV input.
investresearch-b build --spec data/private/manual-prices.json --output data/private/manual-price-bundle
investresearch-b screen --bundle data/private/manual-price-bundle --output reports/generated/private-price-research
```

See [docs/EU_EVIDENCE_AND_MARKET_RIGHTS.md](docs/EU_EVIDENCE_AND_MARKET_RIGHTS.md). Never commit report documents, licensed price files, private portfolios or generated local reports.

### ESEF europeo: primi candidati IFRS senza ranking

L'estrattore facoltativo [`--extract-ifrs`](docs/EU_IXBRL_PARSER.md) legge
solo XHTML/ESEF ZIP locali con checksum; recupera valori candidati di
ricavi e utile in EUR tramite tag IFRS esplicitamente supportati, in un CSV
per revisione manuale. Usa `defusedxml`, limita i byte decompressi realmente
letti e **non** promuove i valori a fondamentali certificati o score di
mercato. Nessun download esterno, upload di report integrali o ordine di borsa.


### EU ESEF live issuer verification (2026-11-02)

Official FY2025 European iXBRL samples have been tested on GitHub Actions for
**Edison and Prysmian**, with numeric checks against issuer income statements.
Both remain provisional human-review candidates; no EU fundamental scores are
automatically promoted. Prysmian required a measured 80MB parser ceiling and
has two semantically different revenue concepts (19,650m / 20,348m EUR).
**Terna** has official PDF references but its ESEF ZIP has not been acquired
and parsed; it is not marked validated. See
[real issuer comparison and unresolved Terna evidence](docs/EU_ESEF_REAL_VALIDATION_PRYSMIAN_TERNA.md)
and [Edison validation](docs/EU_ESEF_REAL_VALIDATION_EDISON.md).

### V3.0.0 R-007 — funnel di ricerca auditable (demo non trade-ready)

Il comando `investresearch-b funnel --bundle data/research/demo --output reports/generated/block_b_funnel`
applica i gate di copertura, qualità e diversificazione; su 7 titoli demo
restituisce correttamente **nessuna shortlist**. Per il contratto di screening
200+ → 30–60 → 5–7 → 0–3 e i limiti sulle fonti reali vedere
[metodologia e controlli R-007](docs/architecture/R007_FUNNEL_RESEARCH.md).

### R-004/R-005 — diagnosi gratuita dei prezzi, senza ranking automatico

Il connettore opzionale `investresearch-b alpha-pilot` usa esclusivamente
il `TIME_SERIES_DAILY` raw `compact` gratuito di Alpha Vantage: una richiesta
autorizzata per un simbolo, output locale ignorato da Git, chiave solo in
`ALPHAVANTAGE_API_KEY`. I prezzi, non rettificati per corporate action,
**non vengono promossi automaticamente** al ranking o a uno stato trade-ready.

Prima di creare account, leggere la [matrice delle utenze e delle dipendenze
V3](docs/architecture/ACCOUNT_AND_SOURCE_READINESS_2026.md) e le
[note del pilot](docs/architecture/ALPHA_PILOT_NOTES.md). Sono già
utilizzabili senza nuove utenze il discovery SEC e i riferimenti FX BCE.

### Decision 2026 — audited tactical multi-asset research (not R-007 global funnel)

The new `investresearch-b tactical` command **re-runs** Block B's source-checked
`screen()` against an actual bundle and the existing R-007 per-instrument
eligibility gates, grouped by instrument class. It reports an auditable research
queue for stocks, ETF UCITS, ETC, ETN and certificates **only when data support
it**; it never lowers R-007's 200+ threshold or creates buy signals.

```bash
investresearch-b tactical --bundle data/research/demo \
  --output reports/generated/block_b_tactical_demo
```

The demo MUST produce **zero real research priorities**, because all its data
are synthetic. The real-source variant requires a personally authorized bundle
and writes only to ignored `data/private/` (or outside the repo).

See [runbook and private B→A transfer](docs/architecture/DECISION_2026_TACTICAL_EXECUTION.md).

### Twelve Data Basic (next verified US price source; no real API call yet)

`investresearch-b twelve-pilot --symbol FSLR --venue XNAS
--live-confirm --acknowledge-personal-terms --output data/private/twelve-FSLR`
makes one local-only 100-bar daily request (`adjust=splits`) using
`TWELVE_DATA_API_KEY` from the environment. Its response is diagnostic,
**not** automatically ranked, with no API key or prices committed/uploaded.

Details: [Twelve Data Basic runbook](docs/architecture/TWELVE_DATA_BASIC_PILOT.md)
and [market source rights triage](docs/architecture/REAL_DATA_PROVIDER_TRIAGE_2026-11-05.md).

### R-009 — Gemini, Groq e OpenRouter (AI facoltativa, opt-in)

Il Research Engine ora dispone di adapter remoti `Gemini`, `Groq` e
`OpenRouter`, oltre all'importazione offline e a Ollama locale.
Nessun provider remoto viene contattato durante `pytest`, il report
quantitativo o la CI standard. La risposta AI resta una controanalisi pubblica
**non verificata**, senza effetto sul ranking, sui dati fiscali o sugli ordini.

I GitHub Actions Secrets hanno nomi `GEMINI_API_KEY`,
`GROQ_API_KEY` e `OPENROUTER_API_KEY`. La sola presenza del secret
non dimostra né piano Free né correttezza della chiave. Per effettuare un test
con una richiesta su dati **totalmente sintetici**, è stato preparato il
workflow manuale `R-009 Manual free-tier public AI check`: sarà
selezionabile dall'interfaccia GitHub **dopo il merge sul branch predefinito**.
Richiede provider e conferma esplicita del piano gratuito. Nessun fallback
a modelli a pagamento, nessun retry, nessuna chiamata pianificata.

Per le istruzioni CLI locali, i modelli consentiti, le condizioni privacy
e i limiti della verifica costi: [R-009 AI counteranalysis](docs/architecture/R009_AI_COUNTERANALYSIS.md).

