"""Readable offline dashboard. Untrusted text HTML-escaped; no javascript execution."""
from __future__ import annotations
import argparse, csv, html, json
from datetime import date
from pathlib import Path
from .cli import ROOT
from .quality import read_strict_csv, audit, to_json, readiness


def e(value):
    return html.escape(str('' if value is None else value), quote=True)


def csv_rows(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def badge(status):
    normalized = str(status).upper()
    if any(marker in normalized for marker in ('BLOCK', 'FAILED')):
        category = 'blocked'
    elif any(marker in normalized for marker in ('INCOMPLETE', 'MISSING', 'REVIEW', 'UNVERIFIED', 'HYPOTHETICAL', 'ESTIMATED', 'DEMO')):
        category = 'pending'
    elif normalized in ('VERIFIED','DOCUMENTED'):
        category = 'verified'
    else:
        category = 'neutral'
    return f'<span class="badge {category}">{e(status)}</span>'


def table(headers, rows):
    body = ''.join('<tr>'+''.join('<td>'+str(cell)+'</td>' for cell in row)+'</tr>' for row in rows)
    return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{e(t)}</th>' for t in headers)+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def html_report(outdir: Path):
    config = json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
    instruments = read_strict_csv(ROOT/'data/snapshots/instruments.csv')
    quotes = read_strict_csv(ROOT/'data/snapshots/verified_quotes.csv')
    decision_file = outdir/'decision_comparison.json'
    decision = json.loads(decision_file.read_text(encoding='utf-8')) if decision_file.exists() else None
    effective_as_of = decision['as_of'] if decision else config['as_of']
    case_mode = decision['mode'] if decision else 'NO_CASE'
    is_demo = case_mode == 'SYNTHETIC_DEMONSTRATION_NOT_PERSONAL_HOLDINGS'
    as_of = date.fromisoformat(effective_as_of)
    gates = audit(instruments, quotes, as_of, settings=config)
    byquote = {r['id']:r for r in quotes}
    byid = {r['id']:r for r in instruments}
    scenarios = csv_rows(outdir/'portfolio_scenarios.csv')
    blocked = sum(x.severity=='BLOCKED' for x in gates)
    incomplete = sum(x.severity=='INCOMPLETE' for x in gates)
    reviewed = sum(x.severity=='REVIEW' for x in gates)
    rows=[]
    for inst in instruments:
        q=byquote.get(inst['id'])
        status=readiness(gates,inst['id'])
        rows.append([e(inst['name']),e(inst['isin']),e(inst['sector']),
            e(q['price']+' '+q['currency']) if q else badge('MISSING'),
            badge(status['research_readiness']),badge(status['shortlist_readiness']),
            badge(status['pretrade_readiness'])])
    scenario_rows = [[e(x['portfolio']),e(x['scenario']),e(x['invested_eur']),
                     e(x['cash_eur']),e(x['net_pnl_excluding_market_spread_eur']),
                     badge(x.get('scenario_status', 'HYPOTHETICAL_LEGACY_UNVERIFIED'))] for x in scenarios]
    decision_rows=[]
    if decision:
        b=decision['B_REALIZE_EXISTING'];c=decision['C_NEW_INVESTMENT']
        decision_rows=[['A — Non intervenire','€0','€0','€0','€0',badge('BASELINE_NO_TRADES')],
                       ['B — Posizioni esistenti',e(b['eligible_net_gain_eur']),
                        e(b['wallet']['potential_tax_avoided_eur']),e(b['estimated_income_tax_eur']),
                        e(b['estimated_incremental_tax_and_execution_effect_eur']),badge(b['status'])],
                       ['C — Nuovo acquisto, ipotetico',e(c['eligible_gain_eur']),
                        e(c['wallet']['potential_tax_avoided_eur']),e(c['estimated_income_tax_eur']),
                        'P/L ipotetico dopo imposte €'+e(c['economic_profit_after_estimated_tax_eur']),badge(c['status'])]]
    analysis='<p>Nessuna ricerca AI effettuata. Le analisi quantitative sono separate dai commenti AI.</p>'
    deep = outdir/'DEEP_RESEARCH.md'
    manifest = outdir/'research_manifest.json'
    if deep.exists() and manifest.exists():
        m=json.loads(manifest.read_text(encoding='utf-8'))
        if m.get('status')=='AI_RESEARCH_COMPLETED_NOT_FACT_CHECKED':
            analysis=f'<p>{badge("AI-ASSISTED / UNVERIFIED")}</p><details><summary>Mostra la relazione</summary><pre>{e(deep.read_text(encoding="utf-8"))}</pre></details>'
    warnings=[[badge(x.severity),e(x.gate),e(x.stage),e(x.message)] for x in gates]
    style='''<style>:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#172337;background:#f4f6fa}body{max-width:1150px;margin:0 auto;padding:30px 18px;line-height:1.55}h1{margin:0}h2{margin-top:30px}p,.muted{color:#536074}.hero{background:#182842;color:white;border-radius:14px;padding:25px}.hero p{color:#e0e9f1}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}.card{border-radius:12px;background:white;border:1px solid #e2e7ed;padding:15px}.metric{font-size:1.5rem;font-weight:800}.scroll{overflow-x:auto;background:white;border:1px solid #d9e2ed;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:.85rem}th,td{text-align:left;vertical-align:top;padding:11px;border-bottom:1px solid #e6e9ef}th{white-space:nowrap;background:#eff3f8}.badge{display:inline-block;border-radius:13px;font-size:.69rem;font-weight:700;padding:3px 8px;white-space:nowrap}.blocked{color:#842d21;background:#ffe5e0}.pending{color:#754a09;background:#fff0d1}.verified{color:#1d653d;background:#e1f5e7}.neutral{color:#4a5563;background:#e8eef3}.notice{background:#fff1df;padding:14px;border-left:4px solid #bf761c}pre{background:white;border:1px solid #eee;padding:15px;white-space:pre-wrap;overflow-wrap:anywhere}details summary{cursor:pointer}</style>'''
    content=f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investment Research V3 — Block A</title>{style}</head><body>
    <div class="hero"><h1>Investment Research — V3</h1><p>Integrità, costo fiscale e scenari dimostrativi · riferimento {e(effective_as_of)}</p><p>Non sono consigli operativi, quotazioni in tempo reale o ordini di Borsa.</p></div>
    <div class="cards"><div class="card"><div class="muted">Capitale dimostrativo</div><div class="metric">€{e(config['capital_eur'])}</div></div><div class="card"><div class="muted">Minusvalenze dichiarate</div><div class="metric">€{e(config['loss_carryforward_eur'])}</div></div><div class="card"><div class="muted">Copertura prezzi storici</div><div class="metric">{len(quotes)}/{len(instruments)}</div></div><div class="card"><div class="muted">Blocchi · Incompleti · Da rivedere</div><div class="metric">{blocked} · {incomplete} · {reviewed}</div></div></div>
    <div class="notice"><strong>Attenzione:</strong> prezzi del catalogo: snapshot {e(config['market_data_last_session'])}, non bid/ask eseguibili. Input confronto A/B/C: {e('DIMOSTRATIVO' if is_demo else 'FORNITO DALL’UTENTE / NON VERIFICATO')}.</div>
    <h2>Alternative decisionali — {e('esempio dimostrativo' if is_demo else 'input fornito dall’utente, non verificato')}</h2>
    {table(['Alternativa','Guadagno diverso dopo perdite correnti €','Imposta teoricamente evitata €','Imposta stimata €','Effetto economico parziale €','Stato'],decision_rows)}
    <p class="muted">Effetto economico B = imposta evitata − imposte scatenate − costi espliciti di vendita; NON equivale al profitto totale, ignora un eventuale riacquisto. C mostra P/L ipotetico dopo imposte, non rendimento atteso. Quote, costi e saldo fiscale non verificati.</p>
    <h2>Universo e stati distinti</h2>
    {table(['Strumento','ISIN','Settore','Prezzo riferimento','Ricerca','Shortlist','Pre-negoziazione'],rows)}
    <h2>Stress test ipotetici</h2>
    {table(['Portafoglio','Caso','Investito €','Cassa €','P/L ipotetico €','Stato'],scenario_rows)}
    <p class="muted">Le percentuali delle simulazioni sono scritte nella configurazione: NON derivano da modelli predittivi; non includono spread eseguibili.</p>
    <h2>Ricerca macro e fondamentale</h2>{analysis}
    <h2>Controlli e limiti</h2>{table(['Stato','Controllo','Fase','Descrizione'],warnings)}
    <p class="muted">Guarda DECISION_COMPARISON.md, decision_ledger.json e docs/FISCAL_SOURCES.md per ipotesi, provenienza e metodologia.</p></body></html>'''
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'dashboard.html').write_text(content,encoding='utf-8')
    (outdir/'quality_gates.json').write_text(json.dumps({'as_of':effective_as_of,
        'blocked':blocked,'incomplete':incomplete,'review':reviewed,
        'statuses':to_json(gates)},indent=2,ensure_ascii=False),encoding='utf-8')
    has_ai=deep.exists() and manifest.exists()
    summary=f'''# Investment Research V3 — Block A

- **As-of:** {effective_as_of}; case source: {case_mode}
- **Blocked:** {blocked}; **incomplete:** {incomplete}; **reviews:** {reviewed}
- **Quote coverage:** {len(quotes)}/{len(instruments)}, historical only.
- **Three-way decision demo:** {'GENERATED' if decision_rows else 'MISSING'}
- **Research AI:** {'PRESENT BUT NOT FINANCIALLY VERIFIED' if has_ai else 'NOT RUN'}
- **Trade readiness:** NOT APPROVED; broker order book and fiscal recognition missing.

Download `investment-research-report` for `dashboard.html`, `DECISION_COMPARISON.md`, and `decision_ledger.json`.
'''
    (outdir/'GITHUB_SUMMARY.md').write_text(summary,encoding='utf-8')
    return blocked


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(ROOT/'reports/generated'))
    args=parser.parse_args(argv)
    count=html_report(Path(args.output))
    print(f'dashboard generated; hard blockers: {count}')

if __name__=='__main__':
    main()
