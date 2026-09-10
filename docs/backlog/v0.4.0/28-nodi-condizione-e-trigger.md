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
- [x] Nodo trigger temporale: a un orario, all'alba, al tramonto
- [x] Nodo trigger su evento e su stato, collegato al motore della issue #27
- [x] Nodo notifica, distinto dall'annuncio vocale
- [x] Simulazione che mostri quale ramo viene percorso
- [x] Validazione del grafo prima del salvataggio: nodi scollegati, cicli, rami senza uscita
- [x] **Salvare il grafo** (vedi sopra: non succedeva)
- [x] **Rendere collegabili i nodi** (vedi sopra: i pin erano invisibili)

Un trigger **a intervalli** («ogni venti minuti») non c'e' e non e' una
dimenticanza: il motore della #27 non ha quel tipo di trigger, e aggiungerlo
qui vorrebbe dire aggiungerlo li' — e' lavoro della #27, non di questa scheda.

## Criteri di accettazione

- [x] Una routine con una condizione percorre il ramo corretto in esecuzione reale
- [x] Una routine con trigger all'alba scatta all'alba — il nodo genera **una
      regola del motore della #27**, che era gia' capace di programmare
      l'alba; nessun secondo scheduler
- [x] Un grafo non valido non puo' essere salvato, e l'errore dice cosa non va

## Come funzionano i nodi trigger

Un nodo trigger porta in `data.trigger` **lo stesso vocabolario** di
`domain/regole.py`: `orario`, `alba`, `tramonto`, `stato`, `evento`, piu'
`voce` — che e' il ripiego, ed e' cio' che ogni routine salvata finora ha.

Al salvataggio, `MotoreRegole.sincronizza_dal_grafo` traduce ogni innesco
automatico in una regola con una sola azione: attiva questa routine. La
sincronizzazione e' **completa**, non incrementale: quello che il disegno non
chiede piu' viene cancellato, altrimenti resterebbe dietro la regola di un
nodo tolto — qualcosa che si accende e nessuno sa perche'. Le regole generate
portano `origine = grafo:<id della routine>`, che e' come si ritrovano.

Due cose che la sincronizzazione **non** fa: non tocca le regole scritte a
mano, e non riaccende una regola generata che qualcuno aveva disattivato.

### Difetti trovati strada facendo

**Un innesco incompleto non dava nessun errore.** `domain/regole` ha un
ripiego per ogni campo — le sette del mattino se l'ora manca — e i ripieghi
sono giusti per chi scrive una regola a mano, sbagliati per chi ha disegnato
un nodo e non l'ha compilato. Una routine che scatta alle sette invece che
alle ventitre' non sembra rotta: sembra sbagliata. Ora `perche_non_scattera`
lo dice e il grafo non si salva.

**La simulazione dell'editor percorreva tutti gli archi.** Era una visita in
ampiezza scritta dentro la pagina: lo stesso difetto dell'esecutore prima di
questa scheda, e mostrava una condizione che accende entrambi i rami — l'unica
cosa che una condizione non fa. Adesso la domanda la fa `/api/modes/simula`
allo stesso codice che esegue la routine.

**Un innesco con un cavo in ingresso non e' un innesco.** L'esecutore lo
salta e prosegue, quindi il disegno mostra qualcosa che non innesca niente.
Ora e' un problema di validazione.

## Cosa resta

Le regole del motore della #27 **non hanno una schermata**: l'API c'e', la
dashboard no. Chi disegna un innesco automatico non ha modo di vedere le
regole che ne nascono, ne' di zittirne una senza tornare nell'editor. Non e'
lavoro di questa scheda — e' una schermata mancante della #27 — ed e' scritto
qui perche' e' venuto fuori lavorandoci.

## Da verificare in casa

- [ ] Aprire l'editor, trascinare due nodi e collegarli: prima di questa
      versione il cavo non partiva.
- [ ] Salvare, chiudere, riaprire: il disegno deve essere ancora li'.
- [ ] Aggiungere una condizione, collegare entrambe le uscite ed eseguire la
      routine con la condizione vera e poi falsa.
- [ ] Premere «Simula Flusso» con una condizione nel mezzo: deve accendersi
      **un ramo solo**, e sotto la condizione deve comparire il perche'.
- [ ] Mettere un innesco al tramonto, salvare, e la sera guardare se la
      routine parte. E' l'unica prova che conta.
- [ ] Togliere quell'innesco, risalvare, e verificare la sera dopo che **non**
      parte piu'.
