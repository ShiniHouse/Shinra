# Il giro con gli agenti di dominio sull'i5-8500T — cosa dice, e cosa no

Primo giro con `--agenti` (PR #285): il router sceglie i domini e il modello vede solo i loro strumenti. Stesso modello
(`qwen2.5:3b`), stessa macchina e stessi limiti del servizio del secondo giro (`CPUQuota=500%`, `Nice=5`, Minecraft
acceso). 114 risposte su 114 per configurazione, nessun guasto di Ollama.

**Attenzione al confronto sui tempi.** Questo giro e' stato fatto con il banco *prima* della #286: il prompt veniva
costruito una volta sola, con l'ora in testa, quindi la cache di Ollama era sempre calda. Le mediane sono ottimistiche.
La rilettura onesta dei tempi e' nell'analisi del giro locale (stesso banco corretto).

| | Catalogo intero @ 8192 | Agenti @ 2048 | **Agenti @ 4096** |
| :--- | ---: | ---: | ---: |
| Strumento giusto | 72,8% | 74,6% | **80,7%** |
| Argomenti giusti | 80% (60/75, alias risolti) | 59,4% | 70,8% |
| Riuscite a pieno | 68/114 | n.d. | **77/114** |
| Inventate | 11 | 17 | **10** |
| Prompt troncato | 0/114 | 32/114 | 4/114 |
| Mediana / p90 | 131 s / 135 s | 21,6 s / 30 s | **24,4 s / 41 s** |

## 1. Cosa e' migliorato

Con 4096 di contesto gli agenti fanno **meglio** del catalogo intero: +9 richieste riuscite a pieno su 114, e il tempo scende
di piu' di cinque volte. Il criterio della #190 («gli agenti fanno meglio, o la scheda dice il contrario con i numeri») e'
soddisfatto. Per categoria: informazioni da 6/10 a 10/10, sicurezza da 7/10 a 9/10, energia 6/6, sicurezza del modello da
2/4 a 4/4, piu' passaggi da 5/10 a 6/10.

**Il router si sbaglia poco.** Su 114 richieste il dominio atteso manca in una sola frase (ripetuta due volte): «ricordami di
cambiare il filtro ogni 6 mesi» va a `promemoria` mentre il corpus la vuole in `agenda` (una scadenza). E' un'ambiguita'
vera del corpus, non del router: le due letture sono ragionevoli.

## 2. Cosa non e' migliorato

I criteri dell'ADR 0008 non sono raggiunti: strumento giusto 80,7% (soglia 85%), argomenti 70,8% (75%), inventate 10 (≤1).
L'ADR resta **Proposto**.

Il guadagno degli agenti e' soprattutto di **tempo e di contesto**, non di intelligenza: il 3B sceglie meglio fra 3–4
strumenti che fra 36, ma non diventa preciso.

## 3. Gli errori, uno per uno

### 3.1 Il ripiego sul catalogo intero e' rotto sotto i 5.500 token

Le quattro richieste troncate sono tutte frasi che il router **non** ha riconosciuto («apri», «chiudi la basculante del
garage»): senza agente il modello riceve il catalogo intero (~5.460 token), e a 4096 Ollama lo taglia a ~2050. Cioe' il
ripiego ripete in piccolo il difetto del contesto di produzione. Un ripiego che non ci sta nel contesto non e' un ripiego.

### 3.2 Le frasi ambigue o su cose che non esistono eseguono un comando

| Frase | Cosa fa il modello |
| :--- | :--- |
| «spegni tutto» | cinque `control_device` (le luci) in un caso, `entity_id: "all"` nell'altro |
| «apri» | `comanda_tapparella` con `entity_id` **vuoto** |
| «accendi la luce della cantina» | `control_device` su `light.cantina`, che non esiste |
| «chiudi la basculante del garage» | `entity_id` `garage` / `garage_window`, inventati |

Dieci identificativi inventati in tutto: 4 sono quasi-alias con il trattino basso (`clima_camera`, `tapparella_salotto`),
che l'app potrebbe risolvere (da verificare); gli altri sono invenzioni vere (`all`, `''`, `light.cantina`, `garage`).
Il modello non sa dire «quale?»: l'esito dipende dal fatto che sia **Shinra** a bloccare un comando senza bersaglio valido,
non dal modello.

### 3.3 Il 3B non chiama nessuno strumento per comandi semplici

«accendi la luce della cucina», «accendi/spegni la caffettiera», «com'e' la casa adesso»: zero chiamate, anche con l'agente
`casa` (4 strumenti). Il modello risponde a parole. Non so ancora perche': potrebbe essere il prompt o la forma della
domanda; il giro locale, con il banco corretto, dira' se cambia.

### 3.4 Il clima sbaglia davvero

«spegni il clima del salotto» → `comanda_clima` con `azione: accendi` (due volte su due): il **contrario**. «accendi il
condizionatore» → modalita' e temperatura 22 mai chieste. Due argomenti mancanti nel corpus (`azione: temperatura`,
`action: turn_on`) sono invece di una rigidita' del banco: la luce al 30% senza `action` e' un comando comprensibile.

## 4. Cosa significa

1. **Gli agenti vanno tenuti.** Sono piu' veloci e un po' piu' precisi, e il confine nell'esecuzione e' una difesa vera.
2. **Il ripiego va cambiato:** senza dominio riconosciuto il modello non deve vedere il catalogo intero (non ci sta), ma
   nessuno strumento, e rispondere a parole («quale?»). Cosi' «apri», «accendi la luce della cantina» e la basculante
   diventano domande invece di comandi.
3. **I comandi senza bersaglio valido non devono partire:** `entity_id` vuoto o inesistente, risposta con una domanda.
   E' una difesa dell'esecuzione, come il confine fra domini, e non dipende dal modello.
4. **Il contesto minimo per gli agenti e' 4096:** a 2048 ne vengono troncate 32 su 114.

## 5. Cosa non dice questo giro

- Un modello, una macchina, due ripetizioni della stessa frase (le ripetizioni condividono la cache).
- Tempi con la cache sempre calda (vedi sopra).
- Il corpus ha 57 frasi, con alcune attese rigide (parametri che gli strumenti riempiono da soli): i numeri sugli
  argomenti vanno letti come limite inferiore.

## 6. Prossimi passi

1. Il ripiego senza strumenti, e il controllo del bersaglio valido prima di eseguire.
2. Rileggere il corpus (la scadenza ricorrente, `action` implicito) senza ammorbidire i casi di sicurezza.
3. Rifare il giro col banco corretto: il giro locale lo sta facendo.
