---
title: "feat(i18n): separare le stringhe dalla logica"
issue: 36
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: core", "area: frontend"]
---

## Contesto

Le stringhe italiane sono intrecciate alla logica in tutto il progetto, incluse
le espressioni regolari di riconoscimento degli intenti
(`^(accendi|attiva|spegni|disattiva)\s+...`) e le liste di parole chiave del
fast-path. Non e' un problema di traduzione delle etichette: e' la logica di
comprensione a essere monolingue.

## Cosa fare

- [ ] Estrarre le stringhe dell'interfaccia in file di traduzione
- [x] Estrarre gli schemi di intento in una configurazione per lingua — #181
- [ ] Prompt di sistema parametrico sulla lingua
- [ ] Selezione della lingua per utente, non solo per installazione —
      per installazione c'e' dalla #181 (`assistant.language`), per utente no
- [ ] Italiano come lingua di riferimento, inglese come seconda per validare la separazione

## Criteri di accettazione

- [x] Aggiungere una lingua non richiede modifiche al codice della logica —
      #181, e lo prova un test che ne inventa una e la fa capire agli intenti veri
- [ ] Due utenti con lingue diverse ricevono risposte nella propria lingua
- [ ] Nessuna stringa visibile all'utente resta scritta nel codice

## A che punto siamo

**#181 — la comprensione esce dal codice.** Era la meta' che la scheda
chiamava per nome: «non e' un problema di traduzione delle etichette: e' la
logica di comprensione a essere monolingue». I verbi che accendono, le parole
del meteo, l'espressione che riconosce una citta' italiana, le frasi che
aprono l'intervista: erano costanti dentro `casa.py`, `informazioni.py` e
`promemoria.py`, quindi **aggiungere una lingua voleva dire modificare la
logica**.

Adesso stanno in `src/shinra/services/intenti/lingue/it.yaml`, e un file
accanto a quello e' una lingua nuova. La si sceglie con `assistant.language` —
lo stesso campo che era stato **tolto** perche' nessuno lo leggeva, e che
`test_ogni_opzione_di_configurazione_ha_un_consumatore` aveva trovato fra le
opzioni che promettevano qualcosa che il programma non faceva. Il suo commento
diceva: «il linguaggio tornera' con la internazionalizzazione (issue #36), che
e' il lavoro che lo rendera' vero». E' tornato.

Il criterio non e' dichiarato, e' provato:
`test_una_lingua_nuova_non_richiede_di_toccare_il_codice` scrive una lingua
inventata in una cartella temporanea, la mette in configurazione, e chiede
agli intenti **veri** di capirla — e di **non** capire piu' l'italiano, che e'
la meta' che conta: se lo capissero ancora, vorrebbe dire che gli schemi sono
rimasti anche nel codice.

Due cose scoperte scrivendolo:

- il meteo controllava `"domani"` dentro il codice, non fra gli schemi. Ora e'
  `meteo.domani` nel file della lingua;
- la guardia che cerca l'italiano rimasto nel codice, scritta con
  un'espressione regolare, **non guardava niente**: un apostrofo dentro una
  stringa a virgolette doppie sfasa l'accoppiamento delle virgolette, e da li'
  in poi mezzo file spariva. Adesso le stringhe le chiede al tokenizzatore di
  Python. L'ha detto una mutazione.

## Cosa resta

Le **stringhe rivolte all'utente** — le risposte, i messaggi dell'intervista,
le etichette della dashboard — sono ancora nel codice, ed e' voluto: sono un
pezzo a se', e mescolarlo con questo avrebbe reso illeggibile il momento in
cui uno dei due ha rotto qualcosa. Poi il **prompt di sistema parametrico
sulla lingua**, la **scelta per utente** invece che per installazione, e una
**seconda lingua vera** — che e' l'unico modo di scoprire cosa si e'
dimenticato.
