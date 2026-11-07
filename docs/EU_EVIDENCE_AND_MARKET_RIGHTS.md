# Blocco B — disclosure europee e percorso prezzi locale (2026)

## Obiettivo

Questa milestone **non** dichiara completo il ranking su dati reali. Introduce
invece due ingressi verificabili, senza provider a pagamento, senza download
automatici e senza distribuire dati per i quali non conosciamo la licenza:

1. **Bilanci annuali europei:** inventario offline dei documenti XHTML/ESEF ZIP
   e PDF, con checksum, data di pubblicazione dichiarata, data di raccolta e
   identità dell'emittente inserita dall'operatore.
2. **Prezzi storici già disponibili in modo autorizzato:** importazione locale
   di OHLCV CSV, con attestazione esplicita dei diritti per **analisi locale**.
   I diritti dichiarati dall'utente NON sono certificati dal software.

La [Commissione europea](https://finance.ec.europa.eu/financial-markets/company-reporting-and-auditing/company-reporting/transparency-requirements-listed-companies_en)
e [ESMA](https://www.esma.europa.eu/issuer-disclosure/electronic-reporting)
spiegano che gli annual financial reports degli emittenti soggetti alla
Transparency Directive sono in XHTML e, per i conti consolidati IFRS, con
marcatura inline XBRL (iXBRL). **Non** significa che un qualunque documento
scaricato sia corretto, certificato, comparabile con US GAAP o automaticamente
traducibile in ricavi/utile.

[Euronext](https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies)
distingue uso interno, non-display e redistribuzione dei dati di mercato; la
presenza di prezzi pubblicamente consultabili non garantisce che sia consentito
scaricarli in massa o condividerli come dataset. Non è presente alcun bypass.

## Registro documentale ESEF/PDF

Scarica **manualmente** dal sito dell'emittente o dal meccanismo ufficialmente
designato il documento annuale di cui hai legittima disponibilità. **Non**
inserirlo nel GitHub pubblico. Conserva file e spec in `data/private/`.

Copia `config/eu_filings_example.json` in `data/private/eu-filings.json` e
sostituisci tutti i segnaposto. Il percorso `relative_path` deve restare
all'interno della directory che contiene lo spec, oppure dentro `--root` se
specificato. Ricava lo SHA-256 del file in locale:

```bash
python -c "import hashlib,pathlib; p=pathlib.Path('data/private/eu-documents/report.zip'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
investresearch-b eu-filings --spec data/private/eu-filings.json \
  --output reports/generated/private-eu-evidence
```

Campi richiesti: `mode`, `as_of`, `documents[]` con `id`, `issuer_name`,
`isin` (facoltativo ma validato se presente), `format` (`ESEF_ZIP`,
`ESEF_XHTML`, `ANNUAL_PDF`), `source_type`, `relative_path`, `sha256`,
`source_url` HTTPS, `published_date`, `fiscal_year_end` e
`retrieved_at_utc` timezone-aware. Fonti etichettabili come
`ISSUER_INVESTOR_RELATIONS`, `OFFICIALLY_APPOINTED_MECHANISM`,
`EXCHANGE_DISCLOSURE`; queste sono **asserzioni**, non domini certificati.

Il comando controlla:

- dimensione massima 50 MB, file ordinari, niente symlink, percorsi assoluti o
  `..` in input; SHA-256 completo e corrispondente;
- formato PDF/XHTML e presenza di XHTML per pacchetti ESEF ZIP; ZIP con file
  cifrati, traversal, symlink o contenuti troppo espansi vengono rifiutati;
- periodo contabile non futuro rispetto alla data pubblicata, documento
  pubblicato e acquisito entro la data di ricerca `as_of`, nessun recupero
  futuro spacciato per evidenza point-in-time.

Produce solo `EU_REPORT_COVERAGE.json`, `.csv` e `.md` con i **metadati** del
report. **Non copia i documenti e non include percorsi locali**, e non estrae
ancora alcuna metrica finanziaria da iXBRL: score contabile e di mercato =
**nessuno**. I file di output non devono essere pubblicati automaticamente.

### Prossimo incremento europeo

Per estrarre numeri IFRS servono validazione del taxonomy package e delle
extension taxonomy dell'emittente, contesti e periodi XBRL, unità/multipli,
consolidamento, segni, restatement, statement di audit e confronto con il
bilancio leggibile. Nessuno di questi controlli è sostituito dal parser attuale.
Il catalogo europeo richiederà poi mapping documentato per LEI/ISIN/mercato,
non inferito da ticker omonimi.

## Prezzi OHLCV manuali autorizzati per uso locale

Il percorso alternativo non dipende da Stooq o Yahoo. Se disponi **già** di un
CSV giornaliero per il quale hai verificato l'autorizzazione a effettuare
questa elaborazione locale, usa `config/manual_prices_example.json`.

Schema CSV esatto:

```csv
Date,Open,High,Low,Close,Volume
2026-10-29,100,102,99,101,123000
2026-10-30,101,103,100,102,142000
```

I due valori sono **solo un esempio di schema**, non prezzi reali. Imposta
`provider=MANUAL_AUTHORIZED_LOCAL_OHLCV_UNVERIFIED`, `sha256` del file reale,
`source_url` HTTPS dichiarato, `retrieved_at_utc` e l'attestazione esatta
`LOCAL_RESEARCH_RIGHTS_ASSERTED_NOT_VERIFIED`. Questa è una dichiarazione
esplicita di uso autorizzato locale, **non** una licenza confermata dal motore.

```bash
investresearch-b build --spec data/private/manual-prices.json \
  --output data/private/manual-price-bundle
investresearch-b screen --bundle data/private/manual-price-bundle \
  --output reports/generated/private-price-research
```

Per poter ordinare uno strumento servono almeno 61 sedute continue, calendario
2026 supportato, settore ed esposizione verificati, eventuali FX BCE su date
coincidenti, quote fresche e nessuno split non risolto. L'intero report resta
**UNVERIFIED / NOT TRADE READY** e non equivale a un total return corretto per
dividendi, né a un prezzo denaro/lettera negoziabile. Non caricare CSV o bundle
in GitHub pubblico.

### Integrità obbligatoria per **tutte** le fonti esterne

Ogni sorgente esterna importata (non soltanto quella manuale) deve ora avere
SHA-256 dichiarato e verificato; l'assenza dell'hash non viene più accettata.
Le fixture sintetiche mantengono la loro modalità distinta. Questo migliora la
riproducibilità ma **non dimostra l'autenticità** dell'origine del file.

## Confine operativo

I workflow Actions restano offline/sintetici per il ranking e senza scaricare
prezzi Yahoo. La verifica SEC autonoma su `main` rimane separata. La ricerca
fiscale A/B/C per posizioni reali, costo medio certificato, minusvalenze e date
di riconoscimento fiscale resta **privata**, distinta dal Blocco B.

## Estrazione iXBRL conservativa — incremento successivo

È disponibile il percorso **facoltativo** `investresearch-b eu-filings --extract-ifrs`.
Usa `defusedxml` e verifica un sottoinsieme di contesti annuali, unità EUR,
tag `ifrs-full`, scale, segni e trasformazioni numeriche. Crea
`EU_IFRS_CANDIDATES_REVIEW.csv` e **non certifica** i valori estratti.
Per campi, limiti e passaggi di controllo umano consultare
[`EU_IXBRL_PARSER.md`](EU_IXBRL_PARSER.md).

Un esempio di **fonte da cui l'operatore può reperire un package reale** è la
pagina ufficiale [Edison – Assemblea marzo 2026](https://www.edison.it/it/assemblea-degli-azionisti-marzo-2026),
che pubblica il consolidato 2025 in ZIP ESEF e il corrispondente PDF di
revisione. Non abbiamo ancora verificato tramite il parser i suoi byte reali:
nessun risultato Edison è presentato come estratto o verificato.


## Controlli aggiuntivi R-004 / R-005 — 4 novembre 2026

Il percorso `MANUAL_AUTHORIZED_LOCAL_OHLCV_UNVERIFIED` è stato rafforzato
prima di poter considerare un dataset in un ranking di ricerca:

- `retrieved_at_utc` deve contenere **data, ora e timezone UTC esplicita**
  (`Z` oppure `+00:00`): data senza orario, stringhe malformate e offset
  non UTC non sono ammessi;
- la data di acquisizione non deve superare `as_of` e non può essere
  **anteriore all'ultima seduta presente nel CSV**: questo impedisce
  l'inserimento di una serie che apparentemente conosce prezzi futuri;
- `split_dates`, se presente, deve essere un elenco di date valide,
  non duplicate e non successive ad `as_of`;
- uno split dichiarato nella finestra delle ultime 61 sedute mantiene
  bloccato lo score anche quando la variazione dei prezzi non raggiunge il
  gate del 15% (p.es. split 11:10); il salto del 15% resta soltanto
  un *segnale di anomalia*, non prova dell'assenza di corporate action.

Questi controlli sono **solo strutturali**: non verificano indipendentemente
licenza, fonte dell'URL dichiarato, rettifiche di split/dividendi, orario della
chiusura né bid/ask effettivamente negoziabile. Il flag di rischio rimane
`UNVERIFIED / NOT TRADE READY`.

**Evidenza:** [CI Blocco B — 213 test superati](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41826625950).
