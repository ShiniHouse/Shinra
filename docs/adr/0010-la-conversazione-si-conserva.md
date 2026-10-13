# 0010 — Si conserva la conversazione, e in che forma

- **Stato:** Proposto
- **Data:** 2026-10-13
- **Attuazione:** milestone `v0.8.0`, issue #254 (riassunti: #255, #256; finestra: #257; sogno notturno: #258)

> Bozza scritta per essere discussa: **nessuna di queste scelte è decisa** finché il proprietario non porta lo stato a `Accettato`.

## Contesto

`ConversationMemory` vive **solo in RAM**: dieci scambi, mezz'ora, persa al riavvio. Per riassumere i turni vecchi bisogna
conservare qualcosa, e conservare conversazioni è una decisione di privacy, non di comodità. Anche il sogno notturno ha come
materiale conversazionale solo questo.

C'è anche una ragione di qualità, **misurata il 2026-10-13** su `qwen2.5:3b`: una sola risposta inventata nella storia fa imitare
il modello invece di chiamare lo strumento (0 su 3, contro 3 su 3 a storia pulita). Conservare e riassumere senza criterio
rende permanente l'errore.

## Proposta

1. **Si conservano i riassunti, non il testo grezzo.** Il testo grezzo resta in RAM come oggi. Un riassunto è per profilo.
2. **Il riassunto parte dai fatti verificati**: strumenti chiamati e loro esiti, scritti dal codice. Il modello può rendere il testo più
   leggibile, ma una risposta data senza chiamare lo strumento che la produce non entra nel riassunto.
3. **Per chi:** per profilo; mai per gli ospiti; per i minori solo l'argomento, non il testo.
4. **Scadenza:** un riassunto scade dopo un periodo configurabile (proposta: 30 giorni) e «dimentica» lo cancella subito.
5. **Il database non è cifrato a riposo.** Lo si dichiara nella guida: chi ha accesso al disco del server legge i riassunti.
6. **Il riassunto non passa mai da un servizio esterno.** Si fa con il modello locale; con l'opzione esterna spenta nulla esce.

## Alternative scartate

- *Conservare tutto il testo*: più privacy da difendere e nessun vantaggio dimostrato per un modello da 3 miliardi di parametri.
- *Non conservare niente*: il sogno non avrebbe materiale e ogni riavvio azzererebbe il contesto.

## Conseguenze

- Una tabella di riassunti con proprietario e scadenza, nello stesso schema della memoria (ADR 0009).
- Un banco (#269) misura se un riassunto conserva i fatti chiave.
- La finestra adattiva (#257) deve poter scartare i turni sospetti, non solo i più vecchi.

## Da decidere prima dell'accettazione

- Durata predefinita dei riassunti.
- Se i minori hanno un riassunto o nessuno.
