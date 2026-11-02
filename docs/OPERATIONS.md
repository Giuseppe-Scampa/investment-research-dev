# Public demo — operations

The repository has synthetic inputs and has no paid AI execution workflow.

## Local

```bash
python -m pip install -e '.[test]'
pytest -q
investresearch report
python -m investresearch.dashboard
```

To supply personal holdings privately, create `data/private/portfolio_private.json` locally based on `data/fixtures/investment_case_example.json`, set `fixture_kind` to `USER_SUPPLIED_UNVERIFIED`, and provide broker-reported tax unit basis where the schema requires it. Run `investresearch report --case data/private/portfolio_private.json` **only on a trusted computer**. Do not commit the personal data and do not run it in GitHub Actions.

## GitHub Actions

- `CI tests and offline reproducible report`: test/analysis on synthetic fixture.
- `Manual offline analysis (no paid API)`: synthetic report and dashboard; optionally refresh *unverified* historical data through free yfinance.
- `Manual non-executable historical refresh`: optional free data ingestion.

## Interpretation

Results are not brokerage tax records, market orders, actionable prices or validated financial predictions. Check provenance, tax category by ISIN, settlement and applicable fiscal recognition independently before financial actions.
