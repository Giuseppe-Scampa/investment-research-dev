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

- Parser `defusedxml` (non `xml.etree.ElementTree`) con budget di **80 MB** per il documento XHTML (adeguato allo XHTML Prysmian FY2025 misurato a 65.361.070 byte; non rimuove i limiti ZIP e sugli elementi XML) e **200.000 elementi XML**; vietate espansioni entità.
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


### Collaudo live su Edison FY2025: compatibilità Transformation Registry 5

Il job GitHub Actions (solo PR, nessun secret, nessun artifact ESEF) ha scaricato
lo ZIP ufficiale Edison FY2025, SHA-256
`4ab61d8a4a959801cc487711ae0850a524b531f7aacf311ecf09ad7131711232`.
La prima estrazione ha identificato **cinque** fatti IFRS con contesto annuale
non dimensionato e unità EUR, ma **nessuno** è stato convertito perché il
bilancio usa il namespace Transformation Registry 5
`http://www.xbrl.org/inlineXBRL/transformation/2022-02-16`
con regola `num-comma-decimal`. Questo fallimento è stato segnalato come
**incomplete**, anziché come validazione positiva; nessun numero verificato.

Il supporto al formato esatto `num-comma-decimal` e `num-dot-decimal` di
[Registry 5 (XBRL International)](https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2022-02-16/inlineXBRL-transformationRegistry-REC-2022-02-16.html)
è stato aggiunto mantenendo gli stessi controlli stretti su segni, separatori
e scala. Gli altri formati del registro 2022 restano **non supportati**, anche
quando semanticamente simili. Un nuovo job deve confermare quali fatti reali
vengono estratti e il loro eventuale confronto **manuale** con il PDF.

### Esito del secondo smoke live sullo ZIP ufficiale Edison (2026-11-02)

Il job PR sul commit `2b917df` ha scaricato il **medesimo** package ZIP ufficiale
(SHA-256 invariato `4ab61d8a4a959801cc487711ae0850a524b531f7aacf311ecf09ad7131711232`).
Il supporto limitato della Transformation Registry 5 ha permesso di recuperare
**cinque facts EUR dello stesso esercizio**, riconducibili a tre concetti:

| Concetto IFRS | Valore ESEF | Voce PDF Edison, conto economico consolidato, pagina stampata 3 |
|---|---:|---|
| `Revenue` | €17.739.000.000 | Ricavi di vendita: €17.739 milioni |
| `ProfitLoss` | €270.000.000 (tre occorrenze dello stesso importo) | Risultato netto: €270 milioni |
| `ProfitLossAttributableToOwnersOfParent` | €240.000.000 | Risultato netto di competenza di Gruppo: €240 milioni |

**Tutti e cinque** i valori candidati corrispondono numericamente al prospetto
pubblicato (PDF per confronto, non la versione elettronica ufficiale ai sensi
della direttiva Transparency). Il dato `Revenue` coincide con i **ricavi di
vendita**, non con i **totali ricavi** (€17.986 milioni): i due non sono
intercambiabili. Restano 25 fatti dei concetti sorvegliati scartati per periodi
o contesti non annuali/non idonei. Non sono state adottate scorciatoie per
richiamare retroattivamente quei valori.

Il job successivo aggiunge un **gate fail-closed**: verifica che l'hash del
package corrisponda allo snapshot verificato, che tutti e tre i riferimenti
numerici siano presenti e che non esistano valori discordanti tra i
candidati confrontati. Cambiamenti della versione pubblicata comportano una
nuova revisione documentale, non una promozione automatica. Anche se il gate è
verde, `accounting_facts_verified` resta 0 e i dati non sono usati nel ranking.

Fonti per il confronto: [pagina assembleare ufficiale Edison](https://www.edison.it/it/assemblea-degli-azionisti-marzo-2026),
[PDF del consolidato FY2025, pagina 3](https://www.edison.it/sites/default/files/documents/relazione_finanziaria_integrata_annuale_2025_bilancio_consolidato_volume_2_1.pdf)
e [GitHub Actions run di acquisizione ed estrazione](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41445131437).


### Prysmian FY2025: secondo emittente reale, test incrementale

- Documento ufficiale: https://www.prysmian.com/sites/www.prysmian.com/files/media/documents/529900X0H1IO3RS1A464-2025-12-31-1-en.zip (pubblicato nella pagina assembleare del 13 marzo 2026). Il primo probe su GitHub ha misurato **32.658.496 byte** per lo ZIP e **65.361.070 byte** dichiarati per l'XHTML consolidato. Il limite originale di 32MB lo rifiutava correttamente.
- Il parser ora accetta un XHTML fino a 80MB, conservando i limiti di dimensione dello ZIP, il controllo dei byte realmente decompressi, il massimo di 200.000 elementi XML e i limiti sui fatti. Non viene distribuito il file ESEF.
- Riferimenti preliminari dal sito dell'emittente per l'anno 2025: ricavi **19.650 milioni EUR** e utile netto riportato nei comunicati **1.270 milioni EUR**. *Non sono automaticamente equivalenti a uno specifico tag IFRS*, né costituiscono controllo pagina-per-pagina del conto economico consolidato.
- `tools/smoke_prysmian_esef.py` è un controllo live senza credenziali, senza upload di raw file e con output di soli candidati, hash e avvisi. Il probe è best-effort e il successo dei test offline non certifica il risultato live: verificare sempre il log GitHub Actions per il valore `OUTCOME`.
- Nessuna nuova fonte di prezzi è abilitata: licenza, rettifiche corporate actions e diritto di output derivati rimangono aperti.


### Hardening degli identificativi `xbrli:unit` (2 novembre 2026)

Il parser rifiuta unità XBRL con ID assente o ripetuto nell'intero documento,
anche se una delle unità duplicate sarebbe stata ignorata perché USD o con
`divide`. In precedenza due definizioni con lo stesso ID potevano far
accettare come EUR un `unitRef` ambiguo, producendo candidati non affidabili.
I test sintetici coprono collisioni EUR/EUR, EUR/USD, unità a rapporto,
ordine invertito, unità senza ID e documenti validi con più unità distinte.
La modifica mantiene il gate `accounting_facts_verified=0`: non certifica
la correttezza IFRS, non introduce prezzi né ranking operativi.


### Stabilizzazione test e gate di validazione live — 3 novembre 2026

Il timestamp di raccolta dei test sintetici è congelato esplicitamente al
2026-11-02, uguale alla data `as_of` dei rispettivi test; l'acquisizione reale
usa invariabilmente l'orologio UTC effettivo. Un test negativo prova che un
fatto raccolto il 3 novembre **non** può essere presentato come acquisito
entro il 2 novembre. Anche i test Yahoo con snapshot simulati applicano lo
stesso principio senza ricorrere a prezzi reali.

I probe Edison/Prysmian ora distinguono: `0` = confronto numerico candidato
superato, ancora da revisionare; `1` = indisponibilità HTTP/rete della fonte,
non prova di estrazione; `2` = ZIP, parser, LEI, cutoff, checksum o confronto
numerico non valido. Nei job GitHub Actions della PR il codice `2` rende la
CI **rossa**; solo `1` *con il marker esatto di fonte indisponibile* produce
un warning senza bloccare i test offline. Il riepilogo riporta esattamente
`NUMERIC_RECONCILIATION_PASSED_REVIEW_REQUIRED`,
`SOURCE_UNAVAILABLE_NO_VALIDATION` oppure `VALIDATION_FAILED`.
Il verde non costituisce comunque certificazione contabile e, se la fonte
non è raggiungibile, non può essere descritto come collaudo live superato.
