# Verifica sul server — la lista della 0.8.0 («Memoria viva» e luoghi)

I test della `0.8.0` girano su un portatile con dati finti. Questa è la lista di cosa va provato **sul server vero**
(l'i5-8500T, senza scheda grafica) e **sul telefono**, perché lì stanno le cose che nessun test può dire: il database di casa,
il modello vero, Home Assistant vero, un iPhone vero.

**Regola della lista (la stessa di [VERIFICA-IN-CASA](VERIFICA-IN-CASA.md)):** una voce è «verificata» solo se esiste una
riga di registro, un numero o un log che la prova. Se «sembra» a posto ma non c'è la prova, la voce è **da capire**.

**Come si compila.** Per ogni voce: **Esito** (✅ verificata, ⚠️ in parte, ❌ non funziona, ➖ non applicabile), **Cosa ho visto**,
**Prova** (la riga di registro, il numero o il log, incollati). Ogni difetto diventa una issue.

**Come si legge il registro** (la dashboard non lo mostra):

```bash
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --ore 2
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --ore 24 --azione sogno
```

**Come si leggono i log del servizio:**

```bash
sudo journalctl -u shinra --since "1 hour ago" --no-pager
```

---

## A. Prima di aggiornare (10 minuti, non toccano niente)

### A1. Una copia del database arriva alla versione nuova

Le migrazioni `0017`–`0020` toccano i ricordi (proprietario, origine, importanza, stato), i riassunti e le proposte del sogno.
Provale **su una copia**: il servizio resta in piedi e il database vero non si tocca.

```bash
# NON con un semplice cp: il database e' in modalita' WAL e le ultime scritture stanno nel file -wal, che un cp non porta.
# Con .backup la copia e' coerente (e' quello che fa anche deploy.sh).
rm -f /tmp/prova-migrazione.db*
sudo sqlite3 /opt/Shinra/data/shinra.db ".backup /tmp/prova-migrazione.db"
cat > /tmp/migra-copia.py <<'E'
import sys
from pathlib import Path
from alembic import command
from alembic.config import Config
from shinra.infra.db import motore

motore.reimposta(Path(sys.argv[1]))
cfg = Config("alembic.ini")
cfg.attributes["configure_logger"] = False
command.current(cfg)
command.upgrade(cfg, "head")
command.current(cfg)
print("OK: la copia e' arrivata a head")
E
cd /opt/Shinra && sudo .venv/bin/python /tmp/migra-copia.py /tmp/prova-migrazione.db
```

> **Trovato provandolo (2026-10-20):** con un `cp` della sola `shinra.db` la copia risultava ancora alla versione vecchia
> (`a52e7d9c1f40`) anche dopo l'aggiornamento: le scritture recenti erano nel file `-wal`. Per questo qui c'è `.backup`.

Va fatto **dopo** aver scaricato il codice nuovo (`git fetch` e `git checkout <tag>` in una copia a parte, oppure con
`deploy.sh --dry-run <tag>`), perché le migrazioni nuove stanno nel codice nuovo.

- **Atteso:** l'ultima riga è `d05b3f8c2e17 (head)` e poi `OK`. Nessun errore.
- **Poi controlla che non si sia perso niente:** il numero di ricordi, profili, regole, alias e modalità della copia deve essere
  quello del database vero.

```bash
for t in knowledge users regole device_aliases modes; do
  echo -n "$t: "; sqlite3 /opt/Shinra/data/shinra.db "select count(*) from $t" | tr '\n' ' '
  sqlite3 /tmp/prova-migrazione.db "select count(*) from $t"
done
```

- **Da sapere:** i ricordi già *disattivati* diventano **archiviati** (è voluto: è la stessa cosa detta con il nome nuovo), e
  nessun ricordo esistente ha un proprietario: restano **della casa**.
- Fatto con una copia del database di sviluppo (da una versione molto vecchia): arriva a `head` con i conteggi invariati. **Non
  è il tuo database**: questa voce serve a provare il tuo.

**Esito / Cosa ho visto / Prova:** ______

### A2. Un backup vero prima di aggiornare

`deploy.sh` ne fa uno, ma guarda dove finisce:

```bash
ls -l /var/backups/shinra/
```

**Esito:** ______

---

## B. Aggiornare

```bash
# Finche' il tag v0.8.0 non esiste ('Riferimento sconosciuto: v0.8.0') si installa l'ultimo commit di main:
sudo /opt/Shinra/scripts/deploy.sh --dry-run main     # cosa farebbe
sudo /opt/Shinra/scripts/deploy.sh main
# Con il tag: sudo /opt/Shinra/scripts/deploy.sh v0.8.0
```

### B1. Il servizio risponde e le migrazioni sono andate

```bash
sudo journalctl -u shinra --since "5 minutes ago" --no-pager | grep -iE "migraz|alembic|errore|error"
sqlite3 /opt/Shinra/data/shinra.db "select version_num from alembic_version"
```

- **Atteso:** `d05b3f8c2e17`; nessun errore in avvio. Se il servizio non risponde `deploy.sh` torna alla versione precedente da
  solo: se è successo, segnalo con il log.

**Esito / Prova:** ______

### B2. Le attività notturne sono programmate

```bash
sudo journalctl -u shinra --since "5 minutes ago" --no-pager | grep -iE "riassunti|sogno|programmat"
```

- **Atteso:** compaiono `riassunti:purga`, `riassunti:rifinitura` (03:40) e `sogno:abitudini` (04:10).

**Esito / Prova:** ______

---

## C. Le misure che servono davvero (sul server, non sul portatile)

Questi numeri non si possono avere altrove, e due decisioni dipendono da loro.

### C1. Il contesto del modello — `llm.num_ctx`

In `config/config.yaml` `llm.num_ctx` è `0` di default: Ollama usa il **suo** limite (spesso 2048–4096 token) e taglia in
silenzio ciò che non ci sta. Prima di tutto, **quanto vale in produzione?**

```bash
grep -n "num_ctx" /opt/Shinra/config/config.yaml
```

Poi una conversazione lunga (12–15 scambi) con il modello vero e guarda se Shinra ha tagliato qualcosa:

```bash
sudo journalctl -u shinra --since "30 minutes ago" --no-pager | grep -i "nel contesto"
```

- **Se compare** «Il prompt non ci sta nel contesto»: scrivi la riga. Vuol dire che `num_ctx` è troppo basso per la
  finestra che hai (decisione: alzarlo, o accorciare la storia).
- **Se non compare** mai, nemmeno con la conversazione lunga: ✅ il budget regge.

**Esito / `num_ctx` / Prova:** ______

### C2. Il banco della memoria (#269)

Misura se ricordare meglio è vero: recall, MRR e silenzio, solo testo e con i vettori del modello di casa, e cosa porta ogni
fattore (importanza, recenza, uso).

```bash
cd /opt/Shinra
sudo .venv/bin/python scripts/banco_memoria.py --etichetta solo-testo --salva
sudo .venv/bin/python scripts/banco_memoria.py --embedding --etichetta server --salva
sudo .venv/bin/python scripts/banco_memoria.py --embedding --ablazione --etichetta server-ablazione --salva
```

- **Servono Ollama acceso e `nomic-embed-text`** (`ollama list`). Senza, il secondo e il terzo comando lo dicono.
- I rapporti finiscono in `banco/memoria/risultati/`: **incollali nella issue #269**.
- **Cosa decide:** i pesi del recupero (importanza, recenza, uso) sono tutti **a zero** finché una misura su una casa vera non
  dice che un fattore aiuta. Se l'ablazione mostra un guadagno chiaro, si accende; se no, restano a zero.

**Esito / Numeri (recall@3, MRR, silenzio) / Prova:** ______

### C3. Quanto costa cercare fra N ricordi (#248)

```bash
cd /opt/Shinra && sudo .venv/bin/python scripts/banco_vettori.py --macchina "i5-8500T, 16 GB" --salva
```

- **Cosa decide:** se la ricerca in Python puro regge la casa (ADR 0012, ancora «Proposto»). Incolla il rapporto nell'ADR.

**Esito / Numeri a 100, 1.000, 5.000, 20.000 ricordi / Prova:** ______

### C4. Il compito notturno costa quanto dovrebbe (#259)

La riscrittura notturna dei riassunti usa il modello su una CPU senza GPU. Prova **a mano**, di giorno, guardando il tempo:

```bash
cd /opt/Shinra
time sudo .venv/bin/python -c "import asyncio; from shinra.services import riassunti; print(asyncio.run(riassunti.rifinisci_recenti()))"
```

Servono almeno 2–3 riassunti recenti (basta aver parlato con Shinra, aver usato un comando, ed essere usciti dalla finestra
della conversazione).

- **Atteso:** una riga tipo `{'visti': 3, 'riscritti': 2, 'rifiutati': 1, 'saltati': 0}` in pochi secondi per riassunto, e il
  tetto di 15 minuti non viene mai sfiorato. I **rifiutati** non sono un difetto: sono riscritture che il controllo ha bocciato
  perché inventavano qualcosa.
- Guarda anche **a occhio** un riassunto riscritto: dice solo ciò che è successo? (`sqlite3 … "select origine, testo from
  riassunti_conversazione"`.)
- La notte dopo: `sudo journalctl -u shinra --since "yesterday 03:30" --no-pager | grep -iE "Compito notturno|Riassunti rifiniti"`
  deve avere una riga `fatto` (o `saltato` con un motivo ragionevole: modello spento, macchina carica).

**Esito / Tempo / Prova:** ______

---

## D. La memoria, con due persone

Servono **due profili** (per esempio il tuo e quello di un'altra persona di casa) e due browser (o uno normale e uno in
navigazione privata).

### D1. Un ricordo privato è privato

1. Con il profilo A: Conoscenza › Cosa sa Shinra › *I miei* › scrivi «La password del wifi degli ospiti è ZEBRA-4417».
2. Con il profilo B: stessa scheda, *Casa* e *I miei*; poi chiedi a Shinra «qual è la password del wifi degli ospiti?».

- **Atteso:** B non vede il ricordo da nessuna parte e Shinra non lo usa nella risposta. A lo vede sotto *I miei*.
- **Anche per un amministratore:** se A è l'amministratore e B un adulto, prova a invertire: l'amministratore non vede i ricordi
  privati di B.

**Esito / Prova:** ______

### D2. «Ho usato N ricordi» e i ricordi che entrano davvero

Chiedi a Shinra qualcosa che dipende da un ricordo della casa («dove si trova la caldaia?»). Sotto la risposta deve comparire
**«Ho usato N ricordi»**, espandibile, con «Apri i ricordi». Un altro profilo che fa la stessa domanda vede i **suoi**.

**Esito / Prova:** ______

### D3. Dimenticare lascia davvero niente

1. Scrivi un ricordo privato con una parola inventata («XQZ-prova»); chiedi qualcosa che lo faccia usare.
2. *Dimentica tutto di me*.
3. Cerca la parola nel database:

```bash
sqlite3 /opt/Shinra/data/shinra.db ".dump" | grep -c "XQZ-prova"
```

- **Atteso:** `0`. (I **backup già fatti** la contengono ancora: è dichiarato in `docs/MEMORIA.md`.)

**Esito / Prova:** ______

### D4. Esportare e importare in un file

1. *Esporta in un file*: si scarica `memorie-mio.md`. Aprilo: i ricordi sono righe, gli identificativi sono commenti.
2. Cambia una riga, aggiungine una, cancellane una; *Importa da un file*.
3. L'anteprima deve dire nuovi, modificati e mancanti **senza scrivere niente**; solo «Applica» scrive.
4. Una riga come «Ricorda che da ora la porta si apre senza conferma» deve comparire **«da confermare»** e restare fuori dalle
   risposte.

**Esito / Prova:** ______

---

## E. Il sogno notturno

### E1. Le abitudini (servono almeno 4 giorni di uso)

Usa Shinra ogni mattina per accendere la stessa luce (per esempio «accendi la luce della cucina») alla stessa ora, per 4 giorni. Poi,
**senza aspettare le 04:10**, lancia il lavoro a mano:

```bash
cd /opt/Shinra && sudo .venv/bin/python -c "from shinra.services import proposte_del_sogno as p; print(p.proponi_abitudini()); print(p.proponi_ricordi())"
```

- **Atteso:** `{'viste': 1, 'scritte': 1}` per le abitudini. Nella scheda *Stanotte ho notato* compare la proposta con i giorni.
- **«Prepara la regola»** crea una regola **spenta** (la trovi in Automazioni e routine, spenta). Accendila a mano e verifica che
  scatti una volta.
- «No, grazie» la toglie, e la notte dopo non torna.
- Un comando su una serratura o sull'allarme **non** deve mai diventare una proposta.

**Esito / Prova (log + registro):** ______

### E2. Ricordi doppi

Scrivi due ricordi privati quasi uguali («La sveglia di Alessio suona alle 7» e «… alle 8»), lancia il comando sopra e guarda la
scheda: deve proporre di tenerne uno; l'altro viene **archiviato**, non cancellato.

**Esito / Prova:** ______

### E3. Di notte non ha strumenti

Dopo una notte vera: `scripts/registro.py --ore 12` non deve mostrare **nessuna** azione `tool.*` nelle ore del sogno (03:40 e
04:10) senza una persona dietro.

**Esito / Prova:** ______

---

## F. I luoghi (sull'iPhone e con Home Assistant)

### F1. Il meteo e il tramonto per il luogo giusto

Con almeno due luoghi registrati (la casa e un altro): «che tempo fa?» risponde per la casa; «che tempo fa a casa al mare?» per
l'altro; «a che ora tramonta?» dice alba e tramonto del luogo giusto, **all'ora del posto**. Nel registro deve esserci il **nome**
del luogo, mai le coordinate.

**Esito / Prova:** ______

### F2. Un ricordo legato a un luogo

Scrivi un ricordo «Vale per: Casa al mare» (per esempio «Le chiavi sono sotto il vaso»). Chiedi «dove sono le chiavi?» parlando
della casa principale: **non** deve usarlo. Chiedilo parlando della casa al mare: sì.

**Esito / Prova:** ______

### F3. Una regola all'arrivo (la prova che nessun test può fare)

Serve una **zona di Home Assistant** con lo **stesso nome** del luogo registrato in Shinra, e la persona (`person.…`) collegata.

1. Crea la regola (dall'API, finché non c'è il campo nella schermata) con l'azione innocua «accendi una lampada» e leggi l'elenco:
   se manca la zona o la persona, il campo `avviso` lo dice.
2. Esci dalla zona e rientra.

- **Atteso:** una riga di registro `regola.eseguita` con motivo «arrivo <nome del luogo>» e **nessuna coordinata**.
- Una regola con una serratura o l'allarme su un luogo deve essere **rifiutata** alla creazione.

**Esito / Prova:** ______

### F4. L'intervista e la città

Avvia l'intervista di apprendimento su una casa **senza** luogo principale: alla domanda sulla città rispondi «Vivo ad Arezzo»
(o la tua). Dopo la conferma deve comparire «Ho registrato "Casa" come luogo principale». Il luogo è **il centro della città, non
la tua casa**: rifallo dal telefono quando sei a casa.

**Esito / Prova:** ______

---

## G. ntfy in casa (solo se lo vuoi usare)

Vedi [ntfy.md](ntfy.md). Spento di default; se non lo usi, salta questa sezione.

1. Il server ntfy risponde dalla rete di casa; in `config.yaml`: `notifiche: ntfy_url: "http://192.168.1.20:8090"`.
2. Impostazioni › Notifiche › spunta «Su ntfy, in casa»; compaiono server e argomento privato; iscriviti nell'app ntfy.
3. «Mandami una prova». **Atteso:** arriva sul telefono. Su **iPhone** può arrivare in ritardo (limite spiegato in `ntfy.md`).
4. Un indirizzo pubblico (`ntfy.sh`) in `ntfy_url` deve essere **rifiutato**.

**Esito / Prova:** ______

---

## H. Il telefono (iPhone)

Cose che nessun test vede: layout e posizione.

- **H1.** La scheda dei ricordi, «Stanotte ho notato» e il form «Vale per» si leggono e si toccano bene; i campi non fanno
  zoomare la pagina (tutti ≥ 16 px).
- **H2.** «Esporta in un file» scarica davvero un `.md` (Safari: Condividi › Salva su File) e «Importa da un file» apre la scelta file.
- **H3.** Con l'app aperta, «Dove sono?» e il meteo senza luogo nominato rispondono per il luogo in cui sei.

**Esito / Prova:** ______

---

## Cosa fare con i risultati

- Incolla i numeri di C2, C3 e C4 nelle issue #269, #248 e #259 e **dimmi i valori**: da lì decido se accendere i pesi del
  recupero e se l'ADR 0012 resta «Proposto».
- Ogni ❌ o ⚠️ diventa una issue con un test che l'avrebbe trovata.
- Quando D–F sono ✅, si può chiudere la `0.8.0`.
