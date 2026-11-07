# V3 release candidate — integrated source-to-decision engine, November 7 2026

**Scope:** release readiness evidence, not assertion of DONE. No additional
licence, paid API, real brokerage documents, personal data or trade is implied.

## Verified source heads and CI

- Public B PR #2, latest code/docs branch: `d8f5710046db26b0350fd115bddea6b6209fb1b2`.
  [CI 42366784202](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/42366784202):
  541 tests passed; architecture/privacy release boundary PASS; ESEF/ECB
  live compatibility smoke successful; EODHD/Xetra full source smoke skipped.
- Private A PR #2 references that exact public SHA in cross-repo CI. Public
  [architecture and original source-link documentation](R008_SEC_ESEF_ORIGINAL_EVIDENCE_LINK_2026.md)
  is separate from A's private output. [Private A CI 42366859021](https://github.com/Giuseppe-Scampa/investment-research-2026/actions/runs/42366859021):
  178 tests passed and original B executable → private A synthetic full-stack
  crossrepo smoke PASS. Public B cannot certify hidden A contents for third
  parties.
- Both PRs remain open and require current-head review. An independent Codex
  review was requested Nov 7 on PR #2 for each repo; request is **not** an
  approval. Do not substitute prior reviews of older commits.

## Software implementation vs operational evidence

| Gate | Software now implemented | Real-world release evidence |
| --- | --- | --- |
| R-001/M1 | Source identity, 2026 calendars, hash/provenance, fail-closed checks | Broker/security identity and original source accuracy still unverified |
| R-002/R-003/M2 | Dated generic tax rules, ETF UCITS capital-vs-diversi regression, A/B/C, private normalized wallet inputs | ISIN-specific tax treatment, bank statements and dated wallet authenticity not provided |
| R-004/R-005/M3 | Free/local Tiingo import, ECB FX, manual Xetra FWB history, split/check-box gates, local corporate-action checks | Licensed independent 61+ adjusted price histories across US/EU/multiple asset classes missing |
| R-006/R-007/M4 | Independent SEC/Xetra unranked discovery and real-schema candidate funnel, no quota filling | Genuine 200+ screenable historic universe and real 30–60 → 5–7 → optional 0–3 funnel not demonstrated |
| R-008/M4 | Source-bound risk correlation/matrix, illustrative stress, NULL-preserving ratios, SEC/ESEF original annual issuer overlay | Original valuation/market-cap/accounting authentication, non-linear structured-product risk and real portfolio covariance not completed |
| R-009/M5 | Manual opt-in Gemini/Groq/OpenRouter local/remote adapters; local Ollama; two-to-four imported responses | Provider account free-tier/billing and live API smoke, independent semantic citation fact-check missing |
| R-010/M6 | Private dashboard, full decision lineage/ledger with risk, valuation and SEC/ESEF original-source hashes | Independent financial approval and real authenticated case reports missing |
| R-011/R-012 | Public/privacy boundaries, ADR/versioning, CI guards, scoped private artifacts | Historic public Git commits/review disclosure not remediated; ADR-0003 still proposed |
| R-013 | No orders, no executable quote claims | Deliberately no automated trading |

No requirement R-001..R-013 was removed. Any DONE status from previous versions
is preserved only when explicitly warranted by its original criterion.
Synthetic and schema-real test data are **not market observations**.

## Decisions blocked by external constraints

1. **Market sources:** an original authorized history with adjusted prices,
   split/dividend evidence, point-in-time venue+ISIN and licensing permission
   must be made available in private cache. FWB currently needs manually
   downloaded bytes; Tiingo free tier requires personally reviewed account
   and usage rights. No EODHD subscription will be used.
2. **Original filing facts:** verify SEC ticker↔CIK↔ISIN against independently
   documented issuer/exchange identity; verify European ESEF contexts/units
   and reported facts against original filings. The code now links and
   audits source-labelled numbers but cannot authenticate the operator's
   identity crosswalk or declared issuer URL by itself.
3. **Live optional AI:** after independent account free-tier/no-billing
   verification, run each manually on fictional public issuer content using
   exactly one provider per dispatch; provider output and its cited claims
   still require external fact-check. Secrets alone do not prove live success.
4. **Private fiscal and execution controls:** individual ISIN tax
   classifications, broker position/wallet documents and recognition-date
   confirmation remain private and are NOT derived from code fixtures.
5. **Governance/security:** independent current-commit reviews and explicit
   resolution of ADR-0003 and historical public Git exposure; no
   destructive history rewrite or repository visibility change authorized.

**Release rule:** do not merge merely because CI is green. Do not claim V3
operational DONE or produce real-money recommendations until the stated
evidence and governance decisions are recorded. A project may be code-complete
in particular modules while overall milestone acceptance remains PARTIAL.
