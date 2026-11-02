# M3 · estrazione *candidata* da bilanci ESEF europei

**Stato: estrattore limitato, offline, per revisione umana. Non è un validatore ESEF/XBRL e non crea un ranking.**

L'estrazione si basa sullo standard ESEF e sulla XBRL Transformation Rules Registry, ma non certifica né la provenienza del documento né la corretta applicazione della tassonomia societaria. Riferimenti primari:

- [ESMA: Electronic Reporting (ESEF)](https://www.esma.europa.eu/issuer-disclosure/electronic-reporting)
- [ESMA: ESEF Reporting Manual](https://www.esma.europa.eu/sites/default/files/library/esma32-60-254_esef_reporting_manual.pdf)
- [XBRL International: transformation rules, registry 4](https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2020-02-12/inlineXBRL-transformationRegistry-REC-2020-02-12.html)

## Utilizzo locale

1. Scaricare manualmente dal sito dell'emittente o dall'OAM ufficiale un bilancio XHTML oppure il package ESEF ZIP. Conservare i file sotto `data/private/`, **mai nel repository pubblico**.
2. Preparare uno spec come `config/eu_filings_example.json` indicando la fonte HTTPS, il contenuto SHA-256 del file, il periodo fiscale e la data di pubblicazione **dichiarata** (non autenticata dal codice). Se uno ZIP contiene più XHTML, aggiungere `xhtml_member` con il percorso interno esatto da interpretare. Se disponibile, aggiungere `lei` e verificare che corrisponda al codice legale dell'emittente indicato nei contesti.
3. Eseguire esplicitamente:

```bash
investresearch-b eu-filings --spec data/private/eu-filings.json \
  --extract-ifrs --output data/private/eu-ifrs-review
```

L'opzione `--extract-ifrs` è **disattivata per impostazione predefinita**. I tre file di inventario esistenti rimangono disponibili. Il nuovo `EU_IFRS_CANDIDATES_REVIEW.csv` contiene solo i valori candidati e campi vuoti di revisione (`human_review_status`, `report_page_to_check`, `accounting_scope_to_check`); **non è un certificato**. Nessun documento originale viene copiato. L'output, pur derivato da informazioni pubbliche, resta destinato alla verifica locale.

## Cosa viene estratto

Solo `ix:nonFraction` con prefisso correttamente associato a `ifrs-full` nell'IFRS taxonomy ufficiale, nomi di concetto esplicitamente riconosciuti (`Revenue`, `RevenueFromContractsWithCustomers`, `ProfitLoss`, `ProfitLossAttributableToOwnersOfParent`), **unità EUR** e contesti XBRL con periodo di durata 300–390 giorni, senza segmenti/dimensioni e con data di fine coincidente con l'esercizio dichiarato.

Trasformazioni numeriche supportate: `num-dot-decimal`, `num-comma-decimal` secondo registry 2020 e i due equivalenti legacy 2015, con scala, segno, Decimal e controlli di range. Unità diverse, elementi di estensione, concetti non riconosciuti, trasformazioni sconosciute, dati infrannuali, contesti dimensionati e duplicati discordanti **non vengono convertiti in un numero unico inferito**. I motivi dei rifiuti sono riepilogati e i duplicati in conflitto sono segnalati.

Le unità USD/GBP, la tassonomia di estensione e i relativi *anchoring*, le extension calculation linkbases, i contesti non convenzionali, il testo delle note, le note sul consolidamento e i PDF **non sono supportati** per estrazione automatica. Non è possibile affermare che `ProfitLoss` e `ProfitLossAttributableToOwnersOfParent` siano equivalenti. Non sommare valori di società, periodi, valute o concetti diversi.

## Sicurezza dei file non fidati

- Parser `defusedxml` (non `xml.etree.ElementTree`) con budget di **32 MB** per il documento XHTML e **200.000 elementi XML**; vietate espansioni entità.
- Per il contenuto ESEF ZIP: inventario dei membri prima della lettura, rifiuto dei percorsi rischiosi, file cifrati, symlink e nomi duplicati. Si legge solo il membro XHTML scelto, in blocchi di 64 KiB, con limite calcolato sui **byte realmente decompressi**, non soltanto sulle dimensioni riportate nella directory ZIP.
- Non viene eseguito codice, non viene scaricato nulla dalla rete e non vengono caricati payload ESEF negli artefatti GitHub.
- Il modulo **non** è un validatore completo del package ESEF: il controllo delle firme, dei linkbase, delle taxonomy extension, dell'issuer identity e delle dichiarazioni di pubblicazione richiede una verifica indipendente.

## Revisione umana obbligatoria prima di un confronto

Per ogni società finalista, confrontare i valori candidati con il prospetto annuale ufficiale, indicando pagina o nota, ambito consolidato/separato, identificativo LEI/ISIN, IFRS concept ed eventuale estensione/ancoraggio, unità, data pubblicazione ufficiale e se il dato corrisponde alla quota di pertinenza degli azionisti della capogruppo. Registrare eventuali riclassifiche e differenze rispetto agli esercizi precedenti. Per i PDF questi valori vanno inseriti solo tramite un successivo processo di revisione manuale documentata, **non tramite una OCR o lettura automatica non verificata**.

Il contatore `accounting_facts_verified` resta sempre **0** in questa milestone. Nessun dato europeo estratto entra automaticamente nello scoring M4. Il ranking richiederà validazione di prezzi, dividendi/split e licenze, nonché un modello fondamentale coerente per settore.

## Allineamento delle fonti prezzi

Il modulo yfinance rimane esclusivamente locale, opt-in, `UNVERIFIED` e **non redistribuibile** nel workflow pubblico. Per eventuali finalisti, i dati dovranno avere licenza o autorizzazione specifica all'elaborazione prevista, identificativo ISIN e MIC, date, valuta, OHLCV, metodologia di aggiustamento (split/dividendi), fonte seconda per riconciliazione e prezzo effettivamente negoziabile fornito dal broker per il pre-trade. **Una tabella web o un CSV pubblico non implica diritti di download sistematico.**

Criterio per una futura integrazione: due livelli separati (`RESEARCH_UNVERIFIED_LOCAL` e `LICENSED_VALIDATED_SOURCE`), senza promuovere automaticamente il primo al secondo. Finché non esiste documentazione di diritti d'uso e corporate action, il prezzo resta un candidato da revisionare e non è utilizzabile per una raccomandazione operativa.


## Revisione indipendente — controllo di ambiguità, 2 novembre 2026

I contesti XBRL con ID duplicato sono rifiutati **anche quando uno dei contesti
sarebbe stato escluso** per periodo, dimensione, entità o formato. La regola
non usa soltanto gli ID dei contesti selezionati.

Un medesimo indicatore operativo (`REVENUE`) può presentarsi con più concetti IFRS
standard (`Revenue`, `RevenueFromContractsWithCustomers`). La loro mappatura
non ne prova l'equivalenza contabile: se gli importi differiscono, il report
contiene `conflicting_metrics=["REVENUE"]` e
`metric_review.REVENUE.status=CROSS_CONCEPT_VALUE_CONFLICT_REVIEW_REQUIRED`.
Se gli importi coincidono, permane `MULTIPLE_CONCEPTS_SAME_VALUE_SCOPE_REVIEW_REQUIRED`.
Anche più importi discordanti all'interno di un solo concetto vengono segnalati.

Nel CSV di revisione **tutte le righe candidate rimangono visibili** con
`metric_review_status` e `candidate_concepts_for_metric`; il campo
`manual_selected_concept` è intenzionalmente vuoto. La scelta del concetto
richiede confronto con il prospetto, pagina e ambito contabile, annotando
`manual_selection_rationale`. Il motore non sceglie mai automaticamente e
il numero di fondamentali verificati resta zero.

### Validazione reale ancora aperta

Fonte ufficiale di test: bilancio consolidato Edison 2025 in ESEF ZIP e relativo
PDF di bilancio, disponibili nella pagina assembleare di marzo 2026:
https://www.edison.it/it/assemblea-degli-azionisti-marzo-2026 .
Il documento deve essere scaricato localmente e sottoposto a `eu-filings
--extract-ifrs`; il successo dei test con fixture non costituisce un collaudo
su emittenti reali. Conservare ZIP e PDF fuori dal GitHub pubblico.
