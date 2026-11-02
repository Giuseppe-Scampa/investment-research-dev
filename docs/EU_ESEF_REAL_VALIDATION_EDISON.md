# Collaudo reale ESEF — Edison, bilancio consolidato FY2025

**Stato: ZIP ESEF 2025 ufficiale scaricato sul runner GitHub e parser collaudato su dati reali. Cinque fatti IFRS candidati estratti, ricondotti a tre voci contabili, con confronto numerico 5/5 sul PDF. Nessun dato certificato o utilizzato per lo scoring.**

Questo documento è un protocollo di riconciliazione, non un report del parser.
Non integra valori nel motore di ranking e non costituisce consiglio di investimento.

## Documenti ufficiali individuati

- Pagina investitori Edison: https://www.edison.it/it/assemblea-degli-azionisti-marzo-2026
- Package ESEF/iXBRL 2025 (3,65 MB): https://www.edison.it/sites/default/files/documents/529900ws2e20ba5j4l49-2025-12-31-1-it_1.zip
- PDF di confronto del conto economico consolidato (2,64 MB): https://www.edison.it/sites/default/files/documents/relazione_finanziaria_integrata_annuale_2025_bilancio_consolidato_volume_2_1.pdf
- Pubblicazione dichiarata sulla pagina dell'emittente: 26 febbraio 2026.
- Chiusura esercizio: 31 dicembre 2025.
- Il sito dell'emittente indica nel package la cartella `reports/`, contenente `529900WS2E20BA5J4L49-2025-12-31-1-it.xhtml` (la stringa identifica il package; verificare nome e maiuscole dall'archivio effettivo).
- Il PDF di confronto avverte di non costituire la versione ufficiale ai sensi della Transparency Directive. **Lo ZIP ESEF è la fonte primaria da verificare.**

## Valori di controllo dal prospetto PDF, pagina stampata 3 (pagina PDF 3, indice 2)

Valori in **milioni di euro**, trascritti dal prospetto del conto economico consolidato. La colonna 2024 serve come confronto visuale, non per simulare automaticamente un contesto 2024 nella ricerca annuale 2025.

| Voce di bilancio pubblicata | FY2025 (€m) | FY2024 (€m) |
|---|---:|---:|
| Ricavi di vendita | 17.739 | 15.387 |
| Altri ricavi e proventi | 247 | 236 |
| **Totale ricavi** | **17.986** | **15.623** |
| Risultato netto, tutte le componenti | 270 | 446 |
| Risultato netto di competenza di terzi | 30 | 43 |
| Risultato netto di competenza di Gruppo | 240 | 403 |

**Attenzione:** `ifrs-full:Revenue` e `ifrs-full:RevenueFromContractsWithCustomers` non vanno abbinati a priori alla riga «Ricavi di vendita» o alla riga «Totale ricavi»: verificare concetto esatto, ambito, unità, note e tassonomia. Analogamente `ProfitLoss` (270 milioni nel prospetto) non è equivalente a `ProfitLossAttributableToOwnersOfParent` (240 milioni).

## Protocollo di audit del file ZIP reale e controlli ulteriori

1. Calcolare SHA-256 e annotare **URL effettivo**, timestamp di acquisizione, pubblicazione verificata sul sito e file locale; non committare ZIP o PDF nel repository pubblico.
2. Ispezionare elenco ZIP: no traversal, link, cifratura, ZIP bomb o nomi duplicati. Identificare l'esatto `.xhtml` consolidato senza scegliere automaticamente un file alternativo.
3. Eseguire `investresearch-b eu-filings --spec data/private/eu-filings.json --extract-ifrs --output data/private/edison-ifrs-audit` con `fiscal_year_end=2025-12-31`, fonte e LEI dichiarati nello spec.
4. Verificare se i tag IFRS standard supportati producono candidati, e annotare separatamente **estensioni non riconosciute**, registro delle trasformazioni e contesti respinti.
5. Confrontare **ciascun candidato** con il conto economico PDF, pagina 3: medesima voce, esercizio, ambito consolidato, unità EUR e scala. Se vi sono concetti alternativi o dati discordanti, compilare manualmente `manual_selected_concept`, `manual_selection_rationale` e pagina della verifica. Senza motivazione il campo rimane vuoto.
6. Solo dopo confronto col documento primario e un controllo indipendente si potrà aggiungere un processo per promuovere i dati a evidenze verificate. **Il parser V1 lascia `accounting_facts_verified=0` e il ranking disabilitato in ogni caso**.

## Esito attuale

- Parser su fixture: test automatici completati.
- Prospetto pubblico PDF: valori di riferimento identificati e controllati visivamente.
- ZIP ESEF ufficiale: acquisito tramite un job PR dedicato di GitHub Actions, con checksum SHA-256 `4ab61d8a4a959801cc487711ae0850a524b531f7aacf311ecf09ad7131711232`. Lo ZIP è stato usato soltanto nel runner temporaneo; non è stato committato né caricato come artefatto.
- Primo run con parser prudente: **0 candidati**, perché cinque fatti utilizzavano Transformation Registry 5 (2022) non ancora supportata. Il job di diagnostica ha segnalato l'esito incompleto, non lo ha spacciato per validazione.
- Secondo run dopo supporto mirato di `2022-02-16:num-comma-decimal`: **5 facts**, relativi a **3 metriche** (un valore ricavi e uno utile di Gruppo, più tre copie dell'utile netto). Tutti e cinque i confronti numerici con le voci PDF sono concordanti.
- **ESEF Revenue**: €17.739 milioni, corrispondente a «Ricavi di vendita» nel PDF; **non** a «Totale ricavi» di €17.986 milioni. **ProfitLoss**: €270 milioni. **ProfitLossAttributableToOwnersOfParent**: €240 milioni.
- Sono stati scartati 25 facts dei concetti riconosciuti per contesti non corrispondenti alla durata annuale non dimensionata selezionata. Non sono stati recuperati retroattivamente.
- Restano da verificare formalmente validità del taxonomy package, extension e anchoring, duplicazioni nel contesto del modello contabile, consolidate-vs-separate e completo significato economico; `accounting_facts_verified=0` e `market_ranking_count=0`.
- [Run live con estrazione numerica di cinque fatti](https://github.com/Giuseppe-Scampa/investment-research-dev/actions/runs/41445131437); la PR ora contiene anche una guardia su checksum ufficiale e corrispondenza delle tre grandezze, per impedire falsi verdi in futuro.