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

- [ ] Estrarre le stringhe dell'interfaccia in file di traduzione — le frasi del server e il prompt sono fuori dal codice (#203); le etichette della dashboard e i messaggi delle skill no
- [x] Estrarre gli schemi di intento in una configurazione per lingua — #181
- [x] Prompt di sistema parametrico sulla lingua — #203
- [x] Selezione della lingua per utente, non solo per installazione —
      del profilo (#203); vuota vuol dire la lingua dell'installazione
- [x] Italiano come lingua di riferimento, inglese come seconda per validare la separazione — #203

## Criteri di accettazione

- [x] Aggiungere una lingua non richiede modifiche al codice della logica —
      #181, e lo prova un test che ne inventa una e la fa capire agli intenti veri
- [x] Due utenti con lingue diverse ricevono risposte nella propria lingua — #203, e lo provano i test
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

## #203 — la lingua e' di chi parla

La seconda meta': le frasi che Shinra **dice**, e la lingua per persona.

- `it.yaml` e `en.yaml` hanno adesso tre sezioni in piu': `messaggi` (le
  risposte degli intenti, il rifiuto per gli argomenti vietati, gli errori),
  `prompt` (il prompt di sistema, a pezzi) e `calendario` (nomi dei giorni e
  dei mesi, cosi' la data nel prompt non dipende dal locale della macchina).
  Il caricatore controlla **ogni chiave per nome**: una lingua a cui manca
  una frase non si carica, invece di scoppiare in mezzo a una risposta.
- La lingua e' un campo del profilo (`lingua`, migrazione 0014). Vuota vuol
  dire «come la casa»: nessun profilo esistente cambia. Il menu sta nella
  scheda del profilo, e `GET /api/lingue` elenca quelle che si possono
  scegliere.
- Gli intenti leggono `richiesta.schemi`, che e' la lingua di chi ha scritto.
  Il prompt lo sceglie l'agente e lo passa a `get_system_prompt`: `config/`
  sta sotto `services/`, e non puo' importare il caricatore.
- **Scrivere l'inglese ha trovato quattro cose rimaste italiane** nel codice
  che la #181 aveva dato per uscito: le parole che fanno pensare a una
  temperatura di casa, la preposizione che introduce una stanza, gli
  inneschi delle notizie e le parole che decidono se dare gli strumenti al
  modello. Erano costanti dentro `casa.py`, `informazioni.py` e `agent.py`.
- La prova del criterio: un test mette due persone nella stessa casa,
  `it` e `en`, e comanda la stessa luce — ciascuna sente la propria lingua
  e **non capisce** quella dell'altra.

## Cosa resta dopo la #203

- **Timer e promemoria** capiscono solo l'italiano: il parser del «quando»
  (`domain/quando.py`, `timer_engine.parse_timer_or_reminder`) ha le sue
  parole dentro. In inglese la richiesta arriva al modello, che usa il tool.
- **Le etichette della dashboard** (migliaia di stringhe fra HTML e
  JavaScript) e **i messaggi delle skill** (`registry.py`, `ha_tools.py`,
  l'intervista) sono ancora italiani. Il criterio «nessuna stringa visibile
  resta nel codice» non e' raggiunto, e non lo si dichiara raggiunto.
