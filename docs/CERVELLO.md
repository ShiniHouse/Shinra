# Il Cervello — vedere cosa sa e cosa fa la casa

Il Cervello è una scheda della dashboard che disegna **tutto quello che
Shinra sa e fa** come un grafo: stanze, dispositivi, routine, regole,
conoscenza, strumenti e agenti, e come sono collegati. Serve a due cose:
capire perché Shinra ha risposto come ha risposto, e accorgersi di cosa
manca (un dispositivo senza nome, una regola spenta, un modello che non
risponde).

Se non l'hai ancora configurata, parti dai [primi passi](PRIMI-PASSI.md): il
grafo si riempie con quello che gli dai (alias, routine, conoscenza). Se
qualcosa non funziona, c'è [PROBLEMI.md](PROBLEMI.md).

---

## 1. Dove si apre

**Configurazione → Il Cervello** (dal telefono, nel menu in alto). Non è un
quarto ingresso: i tre di ogni giorno restano tre.

Vedi la scheda se hai fatto l'accesso. Un dettaglio sulla riservatezza: la
**conoscenza di casa** compare solo a chi ha il permesso di leggerla, e anche
allora si vede *l'argomento* e *che il fatto esiste*, mai il suo contenuto.

Se la casa è ancora vuota la scheda lo dice e ti porta a dare un nome ai
dispositivi: il grafo si riempie da solo man mano che racconti la casa.

---

## 2. Cosa vedi

In alto, quattro numeri:

| Contatore | Cosa conta |
| :--- | :--- |
| **nodi** | Le cose del grafo: stanze, dispositivi, alias, routine… |
| **collegamenti** | Quali sono legate a quali (un alias *nomina* un dispositivo, un agente *usa* uno strumento) |
| **sistemi attivi** | Quanti dei servizi da cui dipende Shinra rispondono (Home Assistant, il modello, le regole, le notizie, le notifiche) |
| **agenti pronti** | Il modello e gli [agenti di dominio](AGENTI.md) |

### I colori dicono il gruppo

| Colore | Gruppo |
| :--- | :--- |
| ambra | Stanze |
| azzurro | Dispositivi |
| ciano | Alias (i nomi che hai dato ai dispositivi) |
| viola | Routine |
| rosa | Regole |
| verde | Strumenti (le cose che il modello può chiamare) |
| arancio | Agenti |
| verde chiaro | Conoscenza |

Il **nome del gruppo** è scritto anche sul grafo, per chi non distingue bene i
colori. I **sistemi** hanno uno stato, che si legge nel pannello a destra e
nel dettaglio di un nodo:

- **Attivo** — risponde.
- **Fermo** — è spento da te (per esempio Home Assistant disattivato nelle
  impostazioni, o nessuna fonte di notizie). Il pannello dice perché.
- **Non raggiungibile** — doveva rispondere e non lo fa (per esempio Ollama
  spento).

---

## 3. Come ci si muove

- **Clic su un nodo**: a destra compare cos'è, di che tipo, il suo stato e **a
  cosa è collegato** (ogni vicino è un pulsante: ci si cammina dentro).
- **Apri**: per stanze, dispositivi, alias, routine, regole, argomenti e fatti
  di conoscenza il pulsante ti porta alla scheda dove li modifichi (la routine
  si apre nell'editor). Strumenti e agenti non si modificano da qui.
- **Doppio clic** su un nodo equivale a **Apri**.
- **Cerca un nodo**: scrivi «luce cucina» e i nodi che hanno quel nome restano
  accesi, gli altri si spengono quasi del tutto.
- **Zoom** (anche con la rotella), **inquadra tutto** e **schermo intero** sono
  in basso a destra. Si trascina il fondo per spostare la vista, e un nodo per
  spostarlo.
- **Cosa mostrare**: spegni un gruppo (per esempio gli strumenti) se il grafo
  è troppo fitto; **Forze del grafo** regola distanza e attrazione.
- **Da tastiera**: il disegno prende il fuoco con `Tab`, e tutto quello che
  si legge sta anche in un elenco in chiaro sotto, per i lettori di schermo.

Il grafo si rinnova da solo mentre la scheda è aperta e smette quando esci.

---

## 4. Il grafo che si accende

Mentre Shinra lavora, il grafo lo mostra. A destra, **Cosa sta facendo
Shinra** è il racconto in chiaro:

1. arriva una richiesta,
2. se serve, consulta la conoscenza (si accende l'argomento),
3. sceglie uno strumento (si accende lo strumento),
4. se comanda qualcosa, tocca un dispositivo (si accende il dispositivo),
5. risponde.

Il **percorso** della richiesta — dal modello allo strumento al dispositivo —
è una linea tratteggiata, e dura pochi secondi. Un **errore** resta rosso più a
lungo (venti secondi), perché sparire in quattro vorrebbe dire non essersi
accorti che qualcosa non ha funzionato. Con il **movimento ridotto**
attivato nel sistema operativo, i nodi non sfumano: sono accesi o spenti.

**Cosa non vedi mai**: il testo di quello che hai chiesto, i parametri di uno
strumento, un messaggio d'errore. Il grafo dice *dove* Shinra è passata, non
*cosa* le hai detto, perché quegli eventi viaggiano fino al browser. Ognuno
vede soltanto le richieste fatte da lui.

---

## 5. Se non è come te lo aspetti

| Vedi | Probabilmente |
| :--- | :--- |
| «La casa non ha ancora niente da mostrare» | Non hai dato nomi ai dispositivi né scritto routine: parti da [Dai i nomi alle tue cose](PRIMI-PASSI.md#3-dai-i-nomi-alle-tue-cose) |
| Il modello è «non raggiungibile» | Ollama è spento o non risponde: [PROBLEMI.md](PROBLEMI.md#ollama-non-risponde-affatto) |
| Home Assistant è «fermo» | È disattivato nelle impostazioni dell'hub |
| «Non hai il permesso di vedere il Cervello» | Il tuo ruolo non può leggere il grafo: chiedilo a chi amministra la casa |
| Parli e il modello non si accende | La richiesta l'ha risolta un *intento* veloce (una luce, un timer) senza passare dal modello: si accende lo strumento e il dispositivo, non il modello. È voluto: è la strada da meno di due decimi di secondo |
