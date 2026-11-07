# ESEF reale FY2025 — Prysmian e Terna: evidenze e limiti

**Data di esecuzione: 2026-11-02.** Questa nota distingue un vero test di
parsing di un archivio ESEF dall'esame di un report annuale PDF. Tutti i valori
rimangono **candidati** e non sono approvati per ranking, operatività o
validazione completa XBRL.

## Prysmian: ZIP ufficiale scaricato e parser eseguito su GitHub

- Pagina investitori: https://www.prysmian.com/en/company/governance/shareholders-meeting
- ZIP ESEF FY2025: https://www.prysmian.com/sites/www.prysmian.com/files/media/documents/529900X0H1IO3RS1A464-2025-12-31-1-en.zip
- Conto economico consolidato pubblicato nei risultati FY2025 (pagina 12, milioni di euro):
  https://www.prysmian.com/sites/www.prysmian.com/files/media/documents/investors/PR_Prysmian_FY25_26022026.pdf
- LEI dichiarato e verificato nell'XHTML: `529900X0H1IO3RS1A464`.
- SHA-256 dello ZIP ESEF letto sul runner:
  `75bd4db98fcf84a4cb51330fc0b6c6745fc2fa6a82cf89ecbbea739a2c9c0737`.
- Dimensione reale ZIP: **32.658.496 byte**. XHTML consolidato selezionato:
  **65.361.070 byte** dichiarati all'interno dell'archivio; membro compresso
  **32.615.167 byte**. Il tetto iniziale a 32 MB bloccava correttamente il test.
  Ora il limite XHTML è **80.000.000 byte**, con tetto sui byte effettivamente
  decompressi, budget XML e controllo strutturale ZIP ancora attivi.

### Corrispondenze numeriche verificate sul conto economico pubblicato

| Concetto IFRS trovato | Voce distinta del prospetto | Valore ESEF e PDF (€ milioni) |
| --- | --- | ---: |
| `RevenueFromContractsWithCustomers` | Revenues / Ricavi | 19.650 |
| `Revenue` | Total revenues and income / Totale ricavi e proventi | 20.348 |
| `ProfitLoss` | Net result / Risultato netto consolidato | 1.294 |
| `ProfitLossAttributableToOwnersOfParent` | Group share / Utile di competenza del Gruppo | 1.270 |

Il parser ha prodotto **cinque** fatti candidati: `ProfitLoss` compare due
volte con il medesimo importo. Tutti e cinque corrispondono numericamente al
valore atteso per il **proprio** concetto. Non è lecito sostituire l'uno all'altro:
`Revenue` include anche 192 milioni di variazioni di magazzino e 506 milioni
di altri proventi rispetto ai `RevenueFromContractsWithCustomers`.
Il parser mantiene quindi lo stato `conflicting_metrics=['REVENUE']` e
**non seleziona** alcun concetto contabile per lo scoring.

La verifica automatica fallisce se cambia il checksum dello ZIP, mancano
concetti attesi, cambia la divergenza documentata, un importo non corrisponde
ai controlli numerici (tolleranza 0,5 milioni per arrotondamento) oppure si
tenta di promuovere i risultati a `accounting_facts_verified` o ranking.

**Evidenza live:** GitHub Actions run
https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41456601209
(passaggio da log: `FOUR_DISTINCT_IFRS_CONCEPTS_MATCH_OFFICIAL_PDF_NUMERICALLY_HUMAN_REVIEW_STILL_REQUIRED`).
Nessuno ZIP ESEF o raw price feed è stato caricato come artefatto.

Questa è una **riconciliazione numerica su un prospetto societario ufficiale**
allegato alla comunicazione risultati FY2025; non equivale a controllare
tassonomie e linkbase, opinion di revisione o intero bilancio ESEF consolidato.
Il benchmark non è una fonte dei rendimenti di borsa.

## Terna FY2025: riferimenti ufficiali acquisiti, archivio ESEF non testato

- Relazione finanziaria annuale ufficiale:
  https://download.terna.it/terna/Terna_Relazione_Finanziaria_Annuale_2025_8de9f193139ef49.pdf
- Annual Report in inglese:
  https://download.terna.it/terna/Terna_2025_Annual_Report_8de9f199b1840f9.pdf
- Comunicazione di deposito 20 aprile 2026 (anche su eMarket Storage):
  https://www.terna.it/it/media/comunicati-stampa/dettaglio/deposito-documentazione-20042026
- Risultati ufficiali FY2025:
  https://download.terna.it/terna/Terna_results_31_December_2025_8de8b468f12087e.pdf

| Voce Terna FY2025 | Riferimento (€ milioni) | Stato |
| --- | ---: | --- |
| Ricavi | 4.033,0 | Controllo PDF ufficiale disponibile, **non estratto da ESEF** |
| Utile netto attribuibile agli azionisti | 1.111,5 | Controllo PDF ufficiale disponibile, **non estratto da ESEF** |

Un'altra pagina Terna, `https://www.terna.it/it/investitori/dati-finanziari`,
mostra **4.003** per i ricavi 2025: cifra in contrasto con la relazione
annuale e il comunicato ufficiale (**4.033,0**). Il sistema deve segnalare
l'incoerenza, **non normalizzarla o inventare una correzione**. Prima di
registrare un valore verificato va spiegata e confermata la differenza.

La Relazione Terna contiene l'affermazione della revisione ESEF; tuttavia
**non è stato individuato/scaricato e testato in questo incremento un URL
certo per lo ZIP/XHTML ESEF FY2025**. Non creare un link per tentativi,
non usare un PDF rinominato come XHTML e non presentare i valori sopra come
risultati del parser.

## Criteri per il prossimo gate prima del ranking M4

1. Per Terna: trovare il file XHTML/ZIP da pagina ufficiale o da eMarket
   Storage, conservare URL effettivo e SHA-256, farlo passare nei controlli
   di formato, byte e LEI, poi riconciliare almeno due concetti al PDF.
2. Per Prysmian: separare **ricavi ordinari** da **totale ricavi e proventi**
   nello schema dei fattori, e selezionare la metrica soltanto dopo
   revisione documentata, non per convenienza dello scoring.
3. Per banche e assicurazioni: individuare concetti IFRS specifici
   (`InsuranceRevenue`, linee finanziarie ecc.); non attribuire `Revenue=0`
   alle entità per cui il parser non copre lo schema.
4. Per i prezzi: nessun feed generico è certificato per download sistematico,
   algoritmi, redistribuzione e uso commerciale. Nessun prezzo derivato da Yahoo
   è caricato nei workflow pubblici o promosso a `LICENSED_VALIDATED_SOURCE`.
5. Tutti i dati reali delle posizioni e delle minusvalenze personali rimangono
   **fuori** dal repository pubblico e dal Blocco B.

**Stato:** Edison e Prysmian hanno test iXBRL reali e controlli numerici
positivi su emittenti distinti. Terna ha riferimenti ufficiali leggibili,
ma **non** un parsing ESEF reale superato. PR #2 resta in bozza.
