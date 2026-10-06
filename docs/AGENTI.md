# Gli agenti — chi fa cosa quando Shinra non ha una risposta pronta

Quando chiedi qualcosa a Shinra, la maggior parte delle volte **non passa dal
modello**: un luce, un timer, il meteo li risolve un *intento*, in meno di due
decimi di secondo. Il modello entra solo quando nessun intento ha capito. E lì
c'è un problema pratico: un modello piccolo, davanti a trentasei strumenti, ne
sceglie uno sbagliato — la luce della camera comandata con lo strumento delle
tapparelle — e il suo prompt diventa così lungo da non entrare nel contesto.

Per questo Shinra divide il lavoro in **otto agenti di dominio**. Ognuno vede
**solo i propri strumenti**, e un piccolo *router* decide quale agente prende la
tua frase. Questa guida dice cosa sa fare ciascuno, cosa succede quando il
router sbaglia, e cosa regolare. La decisione è nell'
[ADR 0008](adr/0008-agenti-per-dominio.md); il grafo che li mostra è in
[Il Cervello](CERVELLO.md). Se qualcosa non funziona, c'è
[PROBLEMI.md](PROBLEMI.md).

---

## 1. Gli otto agenti

| Agente | Cosa sa fare | Strumenti |
| :--- | :--- | ---: |
| **casa** | Accendere, spegnere e regolare luci e prese; lo stato della casa; modalità, scene e routine | 4 |
| **clima e tapparelle** | Il clima (modalità, temperatura, ventola) e le tapparelle (aprire, chiudere, percentuale, lamelle) | 4 |
| **dispositivi** | Serratura, TV e media, aspirapolvere, ventilatore | 4 |
| **sicurezza** | Aperture (porte e finestre), allarme, simulazione di presenza | 3 |
| **energia** | In che fascia siamo, quanto si è consumato e speso, quanto costa tenere acceso un apparecchio | 3 |
| **informazioni** | Meteo, notizie, ricerca sul web, enciclopedia | 4 |
| **promemoria** | Aggiungere, elencare e cancellare i promemoria | 3 |
| **agenda** | Liste (la spesa), impegni, scadenze (bollo, filtri, garanzie) | 11 |

Un agente **non è un programma a parte**: è l'elenco degli strumenti di un
dominio, e le regole del prompt sono quelle di sempre. Si vedono nel Cervello,
ciascuno collegato ai suoi strumenti e a nessun altro.

---

## 2. Come sceglie il router

Il router non usa il modello: guarda **le parole** della frase, nella lingua di
chi parla. «Tapparella» porta a *clima e tapparelle*, «consumato» a *energia*,
«meteo» a *informazioni*, «serratura» a *dispositivi*. I file delle lingue
(`src/shinra/services/intenti/lingue/it.yaml` e `en.yaml`, sezione
`agente.domini`) hanno le parole di ogni dominio.

- **Una frase tocca un dominio**: il modello vede solo gli strumenti di quello.
- **Ne tocca due** («chiudi la tapparella e accendi la luce»): ricevono i due
  agenti con più parole riconosciute, mai di più.
- **Non ne riconosce nessuno**: il modello **non riceve strumenti** e risponde
  a parole. Di solito è una domanda: «su quale dispositivo?».

L'ultimo caso è voluto. Una frase come «apri» o «accendi la luce della cantina»
(che la casa non ha) non ha un bersaglio: indovinare vuol dire comandare una
cosa a caso. Prima il modello riceveva tutti gli strumenti, anche se non
ci stavano nel contesto, e provava.

---

## 3. Quando il router sbaglia dominio

Succede, e il danno è piccolo per costruzione.

- Se il router manda la frase all'agente sbagliato, il modello **non ha lo
  strumento giusto**: non può comandare la cosa sbagliata, e di solito dice che
  non può o chiede di precisare. **Riformula nominando la cosa**: «chiudi la
  tapparella del salotto» invece di «chiudi il salotto».
- Se il modello **nomina lo stesso uno strumento che non appartiene all'agente**
  (a memoria, o scrivendolo nel testo), Shinra lo rifiuta: lo dice nel log e non
  esegue niente. Il confine sta nell'esecuzione, non solo nel prompt, perché un
  modello piccolo nomina anche ciò che non vede.
- Se il comando non ha un **bersaglio che esiste** (un dispositivo vuoto o
  inventato) non parte e chiede: «Non conosco nessun dispositivo chiamato…
  Forse intendevi…».
- Le azioni delicate (serrature, allarme, garage) passano **sempre** dalla
  [conferma](CONFERME.md), qualunque agente le abbia chiamate.

Nel log si legge quale agente ha preso la richiesta: `Agenti di dominio scelti:
clima_e_tapparelle`.

---

## 4. Cosa regolare, e cosa aspettarsi

**Il contesto del modello.** Il prompt di un agente pesa da circa 1.100 a 1.900
token; con due agenti arriva a circa 2.600. Il contesto predefinito (1024
token per le risposte brevi, 2048 per le lunghe) è troppo corto: Ollama taglia
l'inizio del prompt **senza dirlo**, e il modello non vede gli strumenti. Shinra
adesso lo scrive nel log («Il prompt riempie tutto il contesto…»). Con gli
agenti conviene:

```yaml
# config/config.yaml
llm:
  num_ctx: 4096
```

Nel banco di prova, a 2048 il prompt veniva tagliato in 32 richieste su 114; a
4096 in 4 e, dopo che le frasi senza dominio hanno smesso di ricevere il catalogo
intero, in nessuna.

**Quanto sono bravi, onestamente.** Misurato con `qwen2.5:3b` sul banco di
prova (57 frasi, due ripetizioni), a 4096: strumento giusto in circa l'80% delle
richieste, argomenti giusti in circa il 70%, e circa 28 secondi a richiesta su
una CPU senza scheda grafica. Il catalogo intero faceva il 73% in 131 secondi.
Gli agenti sono quindi **più veloci e un po' più precisi**, ma un modello di
quella taglia resta incerto su richieste ambigue: «accendi la luce» accende una
luce a caso, «spegni tutto» spegne luci e clima e chiude una tapparella, e il
clima sbaglia spesso. I comandi semplici sono risolti dagli intenti, senza modello.

**Un'avvertenza vera.** Un modello più grande, o una macchina con una scheda
grafica, cambierebbe i tempi di molto: la roadmap lo misura prima di decidere
([ADR 0008](adr/0008-agenti-per-dominio.md)).

---

## 5. Per chi aggiunge uno strumento

Uno strumento sta nel modulo del suo dominio, in `src/shinra/skills/catalogo/`:
è quel modulo a definire l'agente. Non serve toccare il router, solo dire in
`agente.domini` (nei file delle lingue) con quali parole si riconosce. Un test
controlla che ogni strumento appartenga a **un solo** agente e che ogni lingua
nomini tutti i domini. Il resto, in [SVILUPPO.md](SVILUPPO.md).
