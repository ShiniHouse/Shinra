---
title: "feat(canvas): nodi condizione e trigger temporale nell'editor a grafo"
issue: 28
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: frontend"]
---

## Contesto

L'editor visuale a nodi e' il pezzo migliore del progetto, ma supporta solo
quattro tipi di nodo: innesco vocale, dispositivo, ritardo e annuncio vocale.
Il flusso e' quindi sempre lineare: nessuna diramazione, nessuna condizione.

Il motore di esecuzione fa gia' una visita in ampiezza sul grafo con calcolo dei
gradi entranti: la struttura per i rami c'e' gia'.

### Correzione: l'editor non salvava niente, e i cavi non si potevano tirare

*Aggiunto il 2026-09-10, lavorando alla scheda.*

Prima di aggiungere un nodo qualunque sono venuti fuori **due difetti che
rendevano vano tutto il resto**, ed entrambi erano invisibili perche' il primo
nascondeva il secondo:

1. **Le colonne `nodes` ed `edges` non esistevano nella tabella delle
   routine.** L'editor le mandava al salvataggio, il deposito copiava solo i
   campi che conosceva, e il disegno spariva — senza errori, senza avvisi. Di
   conseguenza l'esecutore non ha **mai** visto un grafo in produzione: le sue
   novanta righe di visita in ampiezza erano codice irraggiungibile.
2. **`port-pin` non aveva nessuna CSS** e non e' una classe di Tailwind: i
   pin dei cavi erano `div` a dimensione zero, quindi invisibili e non
   cliccabili. Nell'editor non si e' mai potuto collegare due nodi.

Il secondo non si notava perche' il primo veniva prima: anche riuscendo a
tirare un cavo, il disegno non sarebbe sopravvissuto al salvataggio.

## Cosa fare

- [x] Nodo condizione con due uscite (vero e falso)
- [ ] Nodo trigger temporale: a un orario, a intervalli, all'alba, al tramonto
- [ ] Nodo trigger su evento e su stato, collegato al motore della issue #27
- [x] Nodo notifica, distinto dall'annuncio vocale
- [ ] Simulazione che mostri quale ramo viene percorso — *il motore restituisce
      gia' le decisioni prese; manca il disegno che le illumina*
- [x] Validazione del grafo prima del salvataggio: nodi scollegati, cicli, rami senza uscita
- [x] **Salvare il grafo** (vedi sopra: non succedeva)
- [x] **Rendere collegabili i nodi** (vedi sopra: i pin erano invisibili)

## Criteri di accettazione

- [x] Una routine con una condizione percorre il ramo corretto in esecuzione reale
- [ ] Una routine con trigger all'alba scatta all'alba — *i nodi trigger
      temporali restano da fare, e vanno appoggiati al motore della #27
      invece di costruire un secondo scheduler*
- [x] Un grafo non valido non puo' essere salvato, e l'errore dice cosa non va

## Cosa resta

I nodi **trigger** — orario, alba, tramonto, evento, stato — e la
**simulazione che illumina il ramo percorso**. Il motore restituisce gia'
`decisioni` con il ramo preso e il perche': manca solo il disegno che le usa.

Sui trigger, la scelta e' gia' presa e vale la pena scriverla: un grafo con un
trigger temporale deve diventare **una regola della #27 che esegue la
routine**, non un secondo scheduler. Due motori che programmano la stessa
casa si contendono lo stesso lavoro, e il secondo si scopre solo quando la
luce si accende due volte.

## Da verificare in casa

- [ ] Aprire l'editor, trascinare due nodi e collegarli: prima di questa
      versione il cavo non partiva.
- [ ] Salvare, chiudere, riaprire: il disegno deve essere ancora li'.
- [ ] Aggiungere una condizione, collegare entrambe le uscite ed eseguire la
      routine con la condizione vera e poi falsa.
