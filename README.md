# Investment Research Engine — public technical demonstration

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
