# Public release: privacy and provenance checklist

This is an offline, synthetic source export WITHOUT any Git history. Publish the files as the initial commit of a new repository to establish an independent public history.

- The original development repository must remain private, because cleaning only the latest commit leaves the history accessible when that repository is made public.
- Public settings use fictitious capital, loss allowance, broker, commissions and foreign-exchange conversion costs.
- Original private market-review memo, operational report and billable API integration are omitted.
- Demo fixture and scenario allocations are synthetic. Original real-case files are not included.
- `.gitignore` excludes local personal-case inputs, cache and generated reports.
- Before public release, run `pytest -q`, regenerate the synthetic report and scan all tracked files for personal names, credentials, bank account numbers, private provider keys and unique identifying details.
- Never expose the existing private repository's commits, PR history or Actions artifacts through a visibility change.
- GitHub Actions on this public demo run synthetic data only. Do not enter real private financial inputs or secrets.

A successful automated text scan does not prove the absence of every possible private datum; manually review all financial narrative and datasets before publication.
