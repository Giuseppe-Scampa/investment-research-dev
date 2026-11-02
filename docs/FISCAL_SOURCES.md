# Block A — fonti fiscali, ipotesi e limiti (2026)

**Data di riferimento:** 2026-11-01. Le regole sotto sono una **simulazione di ricerca**, non il risultato fiscale del dossier o una consulenza tributaria certificata. Ogni ISIN finale deve avere classificazione documentale pertinente; una regola di *categoria* non equivale a una validazione individuale.

## Fonti primarie consultate

1. [Art. 67 TUIR, Normattiva — redditi diversi](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.articolo.numero=67&atto.codiceRedazionale=086U0917&atto.dataPubblicazioneGazzetta=1986-12-31), testo di riferimento 2026. Regime dei redditi diversi e plusvalenze finanziarie.
2. [Art. 68 TUIR, Dipartimento delle Finanze](https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&articolo=Articolo+68&codiceOrdinamento=0000000000000680000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B31D694E8-4398-4030-873B-FEAF5A6647F9%7D). Determinazione delle plusvalenze/minusvalenze, nel quadro vigente.
3. [Circolare 19/E del 27 giugno 2014 — Agenzia delle Entrate, archivio MEF](https://def.finanze.it/DocTribFrontend/getPrassiDetail.do?id=%7B7D760861-F923-4C25-B8A1-0CA675E17D1C%7D). Trattamento degli OICR: proventi e guadagni ordinari come redditi di capitale, perdite fiscalmente rilevanti come redditi diversi, con specificità dei costi.
4. [Istruzioni Agenzia Entrate, Redditi PF quadro RT](https://www.agenziaentrate.gov.it/portale/documents/20143/5084961/PF2_2023_Istruzioni_rett.pdf): 48,08% per risultati da titoli pubblici agevolati. Il coefficiente modellato è **0,4808** (rounding legislativo), non esattamente `12,5/26` in precisione infinita.
5. [Legge 30 dicembre 2025 n.199, art. 1, commi 29–31](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=25G00212&atto.dataPubblicazioneGazzetta=2025-12-30): dal 1 gennaio 2026 l'aliquota legale sulle azioni di cui all'art.1 c.491 L.228/2012 è stata portata da 0,2% a 0,4%, ridotta della metà per operazioni su mercati regolamentati ove applicabile. Il software usa **0,2% solo se FTT in scope**; la soggezione del titolo e le esclusioni vanno verificate separatamente.
6. [Calendario negoziazione 2026, Borsa Italiana](https://www.borsaitaliana.it/borsaitaliana/calendario-e-orari-di-negoziazione/calendario-borsa-orari-di-negoziazione.htm): chiusura 24, 25, 31 dicembre, oltre ai weekend.

## Regole implementate e limiti

- **Azioni ordinarie:** differenze positive/negative di cessione classificate genericamente come redditi diversi; dividendi come redditi di capitale. Non include casi particolari su partecipazioni, titoli esteri o soci professionali.
- **ETF/OICR UCITS:** classificazione **asimmetrica** guadagno/perdita nella cessione; i casi concreti richiedono controllo su provenienza e regime.
- **Titoli di Stato agevolati:** plusvalenze/minusvalenze rilevanti ai fini del 26% considerate per **48,08%**; cedole non usano lo zainetto. Le componenti di rateo e scarto di emissione e i casi di acquisto/rimborso non sono qui dettagliati e NON vanno stimati automaticamente.
- **Obbligazioni corporate:** classificazione generale della differenza prezzo di negoziazione come reddito diverso; interesse/cedole capitale. Ratei e scarti richiedono separazione contabile, non presente nel modello A.
- **ETC/ETN/certificati:** **REVIEW_REQUIRED** per guadagno, perdita e proventi. Il motore non li tratta come utilizzabili per compensazione finché non esiste una regola ISIN-specifica supportata da documenti.
- **Tobin Tax:** applicazione condizionata in ingresso per titoli per cui la soggezione sia documentata, non per nazionalità/venue soltanto. Aliquota stress 2026 0,2% su mercati regolamentati eleggibili; verificare liste MEF, capitalizzazione dell'emittente e casi di esenzione.
- **Costi e imposte:** simulazioni dei costi del broker, ancora prive di spread reale, KID, fiscalità dei ratei, stamp duty, condizioni individuali e riconciliazione ufficiale del conto.
- **Zainetto:** saldo `DECLARED` del fixture e capienza per singolo account e regime. Il recupero è teorico, mai considerato un evento registrato nel dossier.
- **Metodologia lotti:** `EXPLICIT_LOT_SELECTION` è un esempio numerico sotto controllo dell'utente e NON rappresenta automaticamente il metodo usato dall'intermediario. `BROKER_REPORTED_AVERAGE` richiede costo medio fiscale documentato. Nessuna assunzione automatica FIFO/LIFO.
- **Date:** trade date e settlement date separati; `fiscal_recognition_date` rimane `null`. Le date fiscali non si ricavano automaticamente dal calendario di negoziazione.
- **Versionamento:** file `config/fiscal/rules_2026.json` valido solo nel periodo 2026. Le regole 2027 non sono implementate e devono essere validate prima dell'uso.

## Test manualmente ricostruibili

- Azione: vendita €1.100, costo fiscale €900 → reddito diverso positivo €200; con zainetto capiente, risparmio teorico €52.
- ETF UCITS: vendita €1.100, costo €900 → reddito di capitale €200, **€0 di compensazione**; vendita €800 con costo €900 → minusvalenza generalmente reddito diverso €100.
- Titolo pubblico agevolato: plusvalenza di prezzo €1.000 → €480,80 equivalenti al 26%; imposta teorica netta €125,008 prima dell'arrotondamento fiscale finale. **Non includere le cedole nello zainetto**.
- Esempio A/B/C: prassi illustrativa con 2 lotti da 10 azioni; attribuzione esplicita di 5+5, base €775, vendita 10×€110 meno €7 di commissioni = €1.093, potenziale guadagno €318. L'ammissibilità effettiva dei costi fiscali va verificata sul caso specifico.

## Non testato / documentazione mancante

- Regole di trade date/settlement/fiscal recognition per gli specifici rapporti bancari.
- Collo di bottiglia e gestione degli strumenti negoziati in valuta differente dall'EUR, inclusi cambi fiscali effettivi.
- IVA/bollo quando applicabili, costi di custodia, French FTT e altre imposte estere.
- FTT su ogni singolo ISIN, oltre alla logica generale.
- Distinzione di cedole, ratei, scarti di emissione sui bond e trattamento di casi speciali.
- Ricompravendita sul medesimo strumento e relativa prassi fiscale.

Questi punti rimangono esplicitamente in stato di verifica; non sono autorizzazioni all'operatività.

## Revisione indipendente novembre 2026 — priorità del regime amministrato

- [D.Lgs. 461/1997, articolo 6, commi 4 e 5 (MEF)](https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&codiceOrdinamento=0000000000000060000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B572FDDF8-FD5B-47E7-8655-06D3950FE23A%7D): per categorie omogenee nel **risparmio amministrato** il costo è *medio ponderato*, non FIFO; le minusvalenze riducono redditi diversi delle operazioni successive, nel medesimo periodo o nei quattro successivi.
- [Approfondimento Altroconsumo sulla sequenza delle compensazioni](https://www.altroconsumo.it/investi/fiscale-e-legale/investimenti-e-fisco/dossier/minusvalenze/come-sfruttare-le-minusvalenze): nel risparmio amministrato le perdite devono in genere precedere i guadagni o essere realizzate nella stessa giornata. Il modello raggruppa operazioni **ipoteticamente realizzate nella stessa data** e applica cronologicamente le perdite, senza compensazione retroattiva.
- [Regola TUIR art. 67, comma 1-bis](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.articolo.numero=67&atto.codiceRedazionale=086U0917&atto.dataPubblicazioneGazzetta=1986-12-31): per il *regime dichiarativo* i criteri legali sui titoli ceduti non devono essere confusi con quelli dell'amministrato; tale ricostruzione non è coperta dal simulatore personale in questa PR.

Il modulo `tax_netting.py` applica quindi perdite 2026 **precedenti o nella stessa data** a guadagni diversi 2026; solo dopo considera le minusvalenze riportate. Le date `realization_date` e la tassonomia dei prodotti sono input di **scenario**, non date e regole certificate dal broker. Redditi di capitale (ad esempio guadagni di ETF armonizzati) non usano lo zainetto; eventuali loro imposte stimate sono riportate separatamente. Le imposte sono simulazioni e non un certificato fiscale.

**Attenzione:** il coefficiente 48,08% (base rilevante: €2.000 × 0,4808 = €961,60) non implica tassare il residuo €1.038,40 al 12,5% *dopo* avere compensato €961,60: sarebbe un calcolo doppio e scorretto. La differenza non è un secondo reddito imponibile.

## Controverifica indipendente del 2 novembre 2026

La [fonte ufficiale MEF, art. 6 D.Lgs. 461/1997 (testo vigente 2026)](https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&codiceOrdinamento=0000000000000060000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B572FDDF8-FD5B-47E7-8655-06D3950FE23A%7D) conferma il costo medio ponderato per categorie omogenee (comma 4) e la possibilità di compensare le perdite con guadagni delle operazioni successive entro i termini prescritti (comma 5). Il testo non prova da solo una specifica convenzione di ordinamento dei movimenti nello **stesso giorno**, né documenta la precedenza delle perdite correnti sulle minusvalenze pregresse in ogni elaborazione bancaria.

**Scelta tecnica prudenziale:** mantenere la simulazione dichiarata (perdite correnti prima dello zainetto storico) come scenario `UNVERIFIED_BROKER_PROCESSING_RULE`, senza trasformarla in un'affermazione normativa certa. Rifiutare il regime dichiarativo, che richiede una metodologia distinta. Le date di realizzo sono controllate come sedute, ma la data di riconoscimento fiscale resta non certificata.
