# Il banco di prova del tool calling

La `0.6.0` poggia su una scommessa: che il modello locale scelga lo strumento
giusto e gli passi gli argomenti giusti — anche con richieste ambigue, anche a
piu' passaggi. Questo banco la misura, **sulla macchina di casa e con il modello
che ci gira**, invece di lasciarla a un'impressione. I numeri decidono quanto
sono ambiziose le schede sugli agenti (#190, #191) e finiscono nell'ADR 0008
(#184).

## Cosa c'e'

| File | Cosa contiene |
| :--- | :--- |
| `corpus.yaml` | 57 richieste in italiano, in 14 categorie, ciascuna con lo strumento e gli argomenti attesi |
| `mondo.yaml` | La casa finta: gli alias, le modalita', e le risposte che danno gli strumenti |
| `risultati/` | Un report (`.md`) e i dati grezzi (`.json`) per ogni giro, con la data |
| `../scripts/banco_tool_calling.py` | Lo script che li esegue |

Le categorie includono quelle che contano di piu' per una casa: le frasi
**ambigue** («accendi la luce» — quale?) e **sconosciute** («la luce della
cantina», che la casa non ha), in cui indovinare e' sbagliato e la risposta giusta
e' non comandare niente; le richieste **a piu' passaggi**; e due tentativi di far
dire o fare al modello cio' che non deve.

## Prima di tutto: quanto pesa il prompt

```bash
cd /opt/Shinra
.venv/bin/python scripts/banco_tool_calling.py --prova
```

Non chiama Ollama. Dice quanto pesano il prompt di sistema e gli schemi dei
trentasei strumenti, e lo confronta con il `num_ctx` che il programma usa in
produzione. Alla data in cui e' scritto questo file: circa **5000 token** contro
**1024**. Se e' cosi', Ollama taglia il contesto prima di rispondere e il modello
sceglie fra strumenti che non ha mai visto: e' una delle cose che il banco misura
(colonna «Troncati»).

## Come si esegue

Una prova veloce, per vedere che funziona (dieci richieste, un modello):

```bash
.venv/bin/python scripts/banco_tool_calling.py --modelli qwen2.5:3b --limite 10
```

Il giro vero, sul modello che usi e su un secondo da confrontare, con il
contesto di produzione e uno che contiene tutto il prompt. **Serve 8192 e non 4096**:
il prompt piu' gli schemi pesano circa 5000 token, e a 4096 Ollama taglia ancora
(la colonna «Troncati» lo dice). Un contesto grande rallenta la lettura del prompt
su CPU: e' esattamente cio' che il banco misura.

```bash
.venv/bin/python scripts/banco_tool_calling.py \
    --modelli qwen2.5:3b qwen2.5:7b \
    --num-ctx produzione 8192 \
    --ripetizioni 2 \
    --macchina "i5-8500T, 16 GB, niente GPU" \
    --etichetta i5-8500t
```

I modelli devono essere gia' scaricati (`ollama pull qwen2.5:7b`). Lo script non
parla con Home Assistant: gli strumenti rispondono con i risultati finti di
`mondo.yaml`, e nessuna luce vera si accende.

**Quanto ci mette.** Dipende dalla macchina e non lo so in anticipo: ogni
richiesta e' una o piu' chiamate a Ollama con un prompt lungo, e su CPU possono
essere decine di secondi ciascuna. Con 57 richieste, 2 modelli, 2 contesti e 2
ripetizioni sono 456 chiamate almeno: comincia da `--limite 10` e da un solo
modello per farti un'idea, e fai girare il resto **quando la casa non ti serve**
(di notte): Ollama e' lo stesso che usa Shinra, e le due cose si rallentano a
vicenda. Con `Ctrl+C` si interrompe. Dopo ogni modello finito il report si salva (con la
sua data), quindi un giro lungo interrotto non perde i modelli gia' misurati;
quello in corso invece si perde, per questo conviene un modello per volta.

## Cosa si misura

| Colonna | Cosa vuol dire |
| :--- | :--- |
| **Strumento giusto** | Su tutte le richieste: ha chiamato lo strumento atteso (o, nelle ambigue, **non** ha comandato niente) |
| **Argomenti giusti** | Fra quelle con uno strumento atteso: ha passato il dispositivo e i valori giusti |
| **Inventate** | Quante volte ha scritto un `entity_id` che la casa non ha. E' il difetto piu' grave: un comando verso un dispositivo inesistente non da' un errore chiaro |
| **Cicli** | Richieste in cui il modello ha continuato a chiamare strumenti fino al limite di quattro giri |
| **Troncati** | Richieste in cui il prompt ha riempito tutto il contesto: Ollama ha tagliato |
| **Token prompt** | Quanti token ha davvero contato Ollama per il prompt |
| **Mediana / p90 s** | Quanto ci mette a rispondere, in secondi. Il p90 e' il tempo che supera una richiesta su dieci |
| **Regge** | Rispetta i criteri proposti qui sotto |

I criteri proposti per dire che un modello regge sono: strumento giusto ≥ 85%,
argomenti giusti ≥ 75%, al piu' una `entity_id` inventata, nessun ciclo e una
mediana di al massimo 8 secondi. **Sono una proposta da discutere nell'ADR 0008**,
non una verita': i numeri veri li da' il banco, e puo' darsi che sulla tua
macchina nessun modello li rispetti — che e' un risultato, non un fallimento.

## Come ci si fida dei numeri

Un banco che sbaglia a contare e' peggio di nessun banco. Per questo ha i suoi
test (`tests/unit/test_banco.py`), che girano in CI e provano senza Ollama:

- il **corpus** e' valido (ogni strumento atteso esiste, ogni argomento e'
  un parametro vero e ogni valore enumerato e' ammesso);
- il **punteggio** e' giusto nei casi che contano: un dispositivo inventato, una
  frase ambigua, l'ordine delle chiamate;
- il **ciclo** e' quello dell'agente: gli strumenti solo se la frase li chiama e
  **solo al primo giro** (per questo una richiesta a piu' passaggi riesce solo se
  le chiamate stanno nella stessa risposta), il rilevamento del contesto
  troncato, i cicli e gli errori.

Cosa **non** garantisce: che il modello si comporti in casa come nel banco. Il
banco usa una casa finta, una persona sola e il solo italiano; non prova la voce
trascritta male da Whisper, che e' il caso piu' difficile.

## Dopo il giro

1. I file in `risultati/` vanno nel repository con una PR: il numero e la
   macchina su cui e' stato misurato valgono solo insieme.
2. La tabella con almeno due modelli e il modello minimo per gli agenti — o la
   frase «nessuno regge, e il piano cambia cosi'» — vanno nella scheda della
   issue #183 e nell'ADR 0008.
3. Ogni modifica al prompt o agli strumenti si rimisura con lo stesso comando:
   e' il modo di sapere se una modifica ha migliorato qualcosa o l'ha solo
   cambiato.
