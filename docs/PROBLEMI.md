# Quando qualcosa non funziona

Ogni voce di questa pagina è un guasto **successo davvero**, in casa o in
fase di installazione. Non è un elenco di cose che potrebbero andare storte:
è l'elenco di quelle che sono andate storte, con il sintomo per come si
presenta e non per come lo si descriverebbe a posteriori.

Il sintomo che rende un guasto caro da cercare è quasi sempre lo stesso:
**risponde 200 e non funziona**. Per quello, la prima cosa da fare è quasi
sempre la stessa:

```bash
journalctl -u shinra -n 100 --no-pager
```

---

## Non riesco a entrare

### Il PIN del primo accesso è scorso via nel log

Compare una volta sola, all'avvio:

```
=== PRIMO ACCESSO ===  PIN per Amministratore: 462783
```

Se l'hai perso non serve reinstallare niente:

```bash
cd /opt/Shinra && .venv/bin/python scripts/imposta_pin.py
```

### La pagina di accesso non mostra nessun profilo

Succede in un'installazione dove il database è nato vuoto senza i dati di
esempio. Nell'immagine Docker è stato un difetto vero: l'immagine partiva
senza `data/examples/`, rispondeva 200, e **nessuno poteva entrare** perché
non esisteva nessun profilo da scegliere. Adesso la CI costruisce l'immagine,
la avvia e prova a entrare a ogni modifica.

Se ti capita su un'installazione manuale, il log dell'avvio dice se il profilo
è stato creato. Se non c'è, `scripts/imposta_pin.py` ne crea uno.

### Dopo un riavvio la dashboard non riceve più niente

Sintomo: la pagina è aperta, sembra viva, ma non si aggiorna più — i timer non
scorrono, le automazioni non compaiono. Nel log del server:

```
"WebSocket /ws/eventi" 403
```

Era un difetto (#159): il canale degli eventi non accettava i dispositivi
fidati, mentre tutto il resto della dashboard sì. Corretto.

Se lo vedi ancora, il motivo è di solito più semplice: **quella scheda non è
autenticata**. Dalla 0.5.0 la dashboard se ne accorge e lo dice, invece di
ritentare in silenzio all'infinito (#161). Ricarica e rifai il PIN.

---

## La chat risponde male, o non fa niente

### Il modello è troppo piccolo

**È il guasto più costoso di tutti**, perché non sembra un guasto: la casa
risponde, le frasi hanno senso, e semplicemente non succede niente. In casa è
girata per settimane con `llama3.2:1b` configurato senza che nessuno se ne
accorgesse.

Cosa serve saperlo:

```bash
grep '^\s*model:' /opt/Shinra/config/config.yaml
ollama list
```

Il modello predefinito è **`qwen2.5:3b`**, e non è una preferenza: supporta i
**tool** in modo nativo. Qui i tool sono tutto — accendere una luce, mettere
un timer, leggere una scadenza. Un modello senza tool risponde e non fa
niente.

Sintomi tipici di un modello troppo piccolo:

- «accendi la luce del salotto» riceve una risposta cortese e la luce resta
  spenta;
- l'intervista di apprendimento dice «non sono riuscita a ricavarne niente di
  preciso» a ogni domanda. Contali:

```bash
journalctl -u shinra --since "-15min" | grep -c "Estrazione non riuscita"
```

Se quel numero non è zero, il modello è il problema. Cambiarlo non richiede un
riavvio: si sceglie dalle impostazioni, e la configurazione viene riletta
subito.

### Ollama non risponde affatto

```
Impossibile contattare Ollama su http://localhost:11434
```

Shinra parte lo stesso e continua a funzionare per tutto ciò che non passa dal
modello — timer, dispositivi, automazioni. Ma la chat no.

```bash
systemctl status ollama
curl -s http://localhost:11434/api/tags | head -c 200
```

### Timeout 524 dietro Cloudflare o un altro proxy

Il modello impiega più del tempo che il proxy concede. Non è un problema di
rete: è il modello troppo pesante per quella CPU. Un modello quantizzato che
risponde in meno di un secondo risolve.

---

## La casa non fa niente di quello che chiedo

### Manca il token di Home Assistant

Senza token Shinra parte, risponde, e non controlla niente. Lo dice nel log
all'avvio, ma è una riga sola che scorre via.

Il token va in `.env`, **mai** in `config.yaml`:

```bash
grep -c SHINRA_HA_TOKEN /opt/Shinra/.env
```

Se risponde `0`, è quello. Dopo averlo messo serve un riavvio del servizio.

> Non incollare mai il contenuto di `.env` o di `config.yaml` in una chat, in
> una issue o in uno screenshot. Se è già successo: **revoca quel token**
> dalla pagina di Home Assistant dove l'hai creato e creane uno nuovo.
> Nasconderlo non serve a niente.

### Il token c'è ma i comandi non arrivano

Prova la connessione dal pulsante in **Impostazioni → Home Assistant**: dice
cosa ha risposto Home Assistant, che è più utile di indovinare. Un token
revocato, un indirizzo sbagliato e un HA spento danno tre risposte diverse.

### I comandi arrivano ma Shinra non capisce di quale luce parli

Non è un guasto: è il passo 3 dei
[primi passi](PRIMI-PASSI.md#3-dai-i-nomi-alle-tue-cose). Finché non hai dato
un nome tuo a `light.yeelight_desk`, «accendi la luce della scrivania» non
può funzionare.

---

## La voce

### Il microfono non parte su Chrome o Safari

Il browser dà accesso al microfono **solo in HTTPS**. Su `http://` il pulsante
c'è e non succede niente. Non è aggirabile: serve un certificato, e il README
ha la configurazione di nginx.

### Le voci sono robotiche

Sono le voci di serie del browser. Nel selettore vocale di Shinra ci sono le
**voci neurali del server** (*Diego*, *Elsa*): sono quelle da scegliere.

### Alexa dice «non posso raggiungere la skill»

Prima il log, che dice il motivo esatto invece di farlo indovinare:

```bash
journalctl -u shinra | grep -i alexa | tail -20
```

Se manca `SHINRA_ALEXA_SKILL_ID`, va messo in `.env`. Se invece è il proxy a
rifiutare le chiamate di Amazon, l'eccezione va ristretta al percorso
`/api/alexa` — non aperta su tutto il sito.

---

## Installazione e aggiornamento

### `python3 -m venv` dice che manca qualcosa

Su Debian `venv` è un pacchetto a parte:

```bash
sudo apt install python3-venv
```

### Il database va preparato?

No. Viene creato e migrato da solo al primo avvio, e a ogni aggiornamento
`deploy.sh` esegue le migrazioni. Non c'è nessun comando da lanciare — ed è
scritto qui perché non dirlo manda a cercarlo.

### Ho aggiornato e la dashboard si comporta come prima

Il browser tiene i file statici finché non cambia l'indirizzo. Shinra attacca
la versione a ogni indirizzo apposta, quindi non dovrebbe succedere; se
succede, un ricaricamento forzato (`Ctrl+F5`) lo conferma in un secondo.

Se invece è il **server** a essere rimasto indietro, il deploy non è arrivato:

```bash
cd /opt/Shinra && git log --oneline -1
systemctl status shinra | head -5
```

### Ho fatto un disastro e voglio tornare indietro

```bash
sudo /opt/Shinra/scripts/deploy.sh --rollback
```

E se il disastro è nei dati e non nel codice, c'è un backup: `deploy.sh` ne fa
uno prima di toccare qualsiasi cosa, e ce n'è anche uno automatico a orario.

```bash
cd /opt/Shinra && .venv/bin/python scripts/salvataggio.py guarda --da data/salvataggi/shinra-....json
.venv/bin/python scripts/salvataggio.py ripristina --da data/salvataggi/shinra-....json --conferma
```

`guarda` dice cosa c'è dentro l'archivio **senza toccare niente**: si guarda
sempre prima di ripristinare.

---

## Cose che sembrano guasti e non lo sono

| Sembra | È |
| :--- | :--- |
| La dashboard è scura per un istante, poi diventa chiara | Era un difetto (#152), corretto: il tema si decide prima del primo pixel. Se lo vedi ancora, il browser ha in cache la pagina vecchia |
| Una scheda si apre vuota | Era un difetto (#153): una destinazione che non esiste adesso torna alla console invece di lasciare il vuoto |
| Il servizio ci mette novanta secondi a fermarsi | Era un difetto (#118): adesso si ferma in pochi secondi |
| Ollama e Home Assistant non ci sono e Shinra parte lo stesso | È voluto. Parte, dice nel log cosa manca, e funziona per tutto il resto |

---

Se il tuo problema non è qui, il log dice quasi sempre qualcosa di utile —
e se non lo dice, quella è a sua volta una cosa da sistemare: apri una issue
con la riga che ti aspettavi di trovare e non c'era.
