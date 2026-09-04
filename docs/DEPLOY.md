# Aggiornamento del server Debian

## Il problema con la procedura attuale

```bash
cd /opt/Shinra && git pull && systemctl restart shinra
```

Funziona finche' nulla va storto, e non ha modo di accorgersi quando qualcosa
va storto. Cinque problemi concreti, in ordine di gravita'.

### 1. Il prossimo `git pull` cancellera' la configurazione del server

Questo e' il punto urgente. `config/config.yaml` e' **tracciato da git** e sul
server contiene il token reale di Home Assistant.

La issue [#07 della v0.1.0](backlog/v0.1.0/07-sec-05-segreti-fuori-da-git.md)
esegue `git rm --cached config/config.yaml`. Per il repository e' la cosa
giusta; ma per **ogni copia che fa `git pull`** quel commit dice «questo file
non fa piu' parte del progetto», e git lo **elimina dalla cartella di lavoro**.

Al primo aggiornamento dopo quella modifica, il server perde configurazione e
token, e il servizio riparte senza sapere piu' come raggiungere Home Assistant.

Non e' un'ipotesi: e' il comportamento normale di git, e succedera' senza
alcun avviso. La messa in sicurezza e' in fondo a questo documento e va fatta
**prima** di unire quella issue.

### 2. Nessun ritorno indietro

Se il nuovo commit non parte, resta solo un servizio fermo e nessun modo
rapido di tornare a com'era. Serve sapere in anticipo da dove si veniva.

### 3. Nessuna verifica

`systemctl restart` ritorna subito: dice che ha *avviato* il processo, non che
il processo *funziona*. Un errore di importazione al primo avvio produce un
comando andato a buon fine e un servizio morto.

### 4. Le dipendenze non vengono installate

Il comando non installa nulla. Dalla v0.2.0 arrivano APScheduler, SQLAlchemy e
altre: senza installazione il servizio non parte piu'.

### 5. Nessuna migrazione

Dalla v0.2.0 lo schema del database evolve. Un aggiornamento senza migrazione
avvia il codice nuovo su uno schema vecchio.

---

## La procedura nuova

```bash
sudo /opt/Shinra/scripts/deploy.sh
```

Lo script, in ordine: rifiuta di partire se ci sono modifiche locali non
salvate; scarica gli aggiornamenti; sceglie **l'ultimo tag di release** invece
dell'ultimo commit; archivia configurazione e dati in
`/var/backups/shinra/`; aggiorna il codice; reinstalla le dipendenze **solo se
sono cambiate**; applica le migrazioni; riavvia; e per trenta secondi verifica
che il servizio risponda davvero. Se non risponde, mostra il log, **torna da
solo alla versione precedente** e riavvia.

> ### Sul server non si esegue mai `git pull` a mano
>
> Non e' una preferenza di stile: `git pull` scavalca tutto cio' che questa
> procedura fa per te. Niente backup, niente messa da parte dello stato,
> nessun riavvio controllato, nessuna verifica di salute, nessun ritorno
> indietro possibile. Lo script fa il `fetch` da solo: non serve anticiparlo.
>
> Succede in buona fede, tipicamente per «prendere prima lo script nuovo».
> Anche in quel caso la risposta e' lanciare lo script: si aggiorna da se'.
>
> Se il pull e' gia' stato fatto, lo script dira' «gia' aggiornato» e non
> fara' nulla — comprese le migrazioni che dovevano accompagnare quel codice.
> Per rimediare, riportare il repository alla versione precedente e rifare
> l'aggiornamento con lo script:
>
> ```bash
> sudo -u "$(stat -c '%U' /opt/Shinra)" git -C /opt/Shinra checkout --force HEAD~1
> sudo /opt/Shinra/scripts/deploy.sh
> ```

### Comandi

```bash
sudo scripts/deploy.sh                # ultima release taggata (consigliato)
sudo scripts/deploy.sh v0.1.0         # una versione precisa
sudo scripts/deploy.sh main           # ultimo commit di main, per provare
sudo scripts/deploy.sh --dry-run      # mostra cosa farebbe, senza farlo
sudo scripts/deploy.sh --rollback     # torna alla versione precedente
sudo scripts/deploy.sh --proteggi-stato   # una volta sola, vedi sotto
```

### Perche' i tag e non `main`

`main` e' protetto e sempre rilasciabile, ma resta il ramo su cui si lavora: un
`git pull` di mercoledi' pomeriggio prende qualunque cosa sia stata unita
un'ora prima. Un tag e' una versione che ha superato i criteri di uscita della
sua fase ed e' stata dichiarata pronta.

La casa e' un ambiente di produzione: ci abitano delle persone. Distribuisci
release, non commit.

---

## Messa in sicurezza, una volta sola

Da eseguire sul server **prima** di unire la issue #07.

### 1. Metti al riparo la configurazione

```bash
cd /opt/Shinra
sudo cp config/config.yaml /root/shinra-config-backup.yaml
sudo chmod 600 /root/shinra-config-backup.yaml
```

Se dopo un aggiornamento futuro il file sparisce, si ripristina da qui.

### 2. Sposta i segreti in un file d'ambiente

```bash
sudo tee /opt/Shinra/.env >/dev/null <<'FINE'
SHINRA_HA_TOKEN=il-tuo-token-vero
SHINRA_HA_URL=http://192.168.x.x:8123
SHINRA_ADMIN_PIN=il-tuo-pin
SHINRA_SESSION_SECRET=
SHINRA_ALEXA_SKILL_ID=amzn1.ask.skill.xxxxxxxx
FINE

sudo chmod 600 /opt/Shinra/.env
sudo chown shinra:shinra /opt/Shinra/.env   # dopo aver creato l'utente, punto 4
```

Genera il segreto di sessione con:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`.env` e' in `.gitignore`: nessun `git pull` potra' toccarlo. Dalla v0.1.0 e'
da li' che il codice legge i segreti.

### 3. Metti al riparo lo stato di questa casa

Non e' solo `config.yaml`. Anche `data/users.json`, `data/knowledge.json`,
`data/device_aliases.json` e `data/sources.json` sono tracciati da git e sul
server contengono i dati reali: gli utenti della famiglia, la conoscenza della
casa, gli alias dei dispositivi. Nel repository ci sono le versioni
dimostrative, ed e' giusto che differiscano.

```bash
sudo /opt/Shinra/scripts/deploy.sh --proteggi-stato
```

Un comando, una volta sola. Fa un backup completo in `/var/backups/shinra/`,
toglie quei file dall'area di lavoro di git e li marca `skip-worktree`, cosi'
nessun aggiornamento puo' piu' sovrascriverli.

> **Non usare mai `git checkout -- .` su questi file.** Sostituirebbe i dati
> della tua casa con quelli dimostrativi del repository. Lo script te lo
> ricorda, ma vale la pena saperlo a priori.

Da solo `skip-worktree` non basterebbe: quando arriva la issue #07, che
rimuove quei file dall'indice, git rifiuterebbe l'aggiornamento con
*«Your local changes would be overwritten by merge»*. Nessun dato perso, ma
il deploy si blocca. Per questo lo script fa un passo in piu': riconosce quali
file di stato l'aggiornamento sta per smettere di tracciare, li mette da
parte, lascia procedere il checkout e li rimette al loro posto subito dopo —
compreso il percorso di ritorno indietro, perche' un ripristino che perde i
dati della casa non e' un ripristino.

### 4. Smetti di far girare il servizio come root

Oggi l'unita' descritta nel README usa `User=root`: un servizio raggiungibile
dalla rete che gira con tutti i privilegi della macchina.

```bash
sudo useradd --system --home /opt/Shinra --shell /usr/sbin/nologin shinra
sudo chown -R shinra:shinra /opt/Shinra
sudo install -m 644 /opt/Shinra/deploy/shinra.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart shinra
sudo systemctl status shinra
```

L'unita' in `deploy/shinra.service` gira come utente dedicato, legge i segreti
da `.env`, tiene il filesystem in sola lettura tranne `data/` e `config/`, e
smette di insistere dopo cinque avvii falliti di fila invece di riavviarsi
all'infinito.

### 5. Prova a vuoto

```bash
sudo /opt/Shinra/scripts/deploy.sh --dry-run
```

Non modifica nulla ed elenca ogni passo. Se l'esito e' quello atteso, la
procedura e' pronta.

---

## Non riesco piu' a entrare

Dalla `v0.1.0` l'autenticazione e' attiva e ogni familiare ha il proprio PIN.
Al primo avvio, se nessuno ne ha uno, ne viene generato uno per
l'amministratore e scritto nel log **una volta sola**.

Se quel messaggio e' gia' scorso via — con `debug: true` uvicorn si riavvia a
ogni scrittura su file, quindi succede in fretta — cercalo in tutto il
giornale, non solo nelle ultime righe:

```bash
sudo journalctl -u shinra --no-pager | grep -i "PRIMO ACCESSO"
```

Se non c'e' piu', si reimposta da riga di comando:

```bash
# chi c'e' e chi ha un PIN
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py --elenco

# imposta un PIN, chiesto senza mostrarlo a schermo
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py alessio

# oppure fanne generare uno
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py alessio --genera
```

Il PIN viene salvato cifrato e riletto dal disco per conferma: scriverlo a
mano in `data/users.json` **non funziona**, perche' li' dentro sta l'hash.

Non serve fermare il servizio. Per chiudere subito le sessioni gia' aperte,
`sudo systemctl restart shinra`.

### Riaprire la casa in fretta

Se c'e' un'emergenza e serve accedere subito, in `config/config.yaml`:

```yaml
security:
  auth_enabled: false
```

Poi `sudo systemctl restart shinra`. Da quel momento chiunque sia sulla rete
di casa comanda l'impianto, e a ogni avvio il log lo ricordera'. E' una
scappatoia, non una configurazione.

---

## Quando qualcosa va storto

```bash
sudo systemctl status shinra              # stato attuale
sudo journalctl -u shinra -n 100 --no-pager   # ultime 100 righe di log
sudo journalctl -u shinra -f              # log in tempo reale
sudo scripts/deploy.sh --rollback         # torna alla versione precedente
ls -lht /var/backups/shinra/              # backup disponibili
```

Ripristino di configurazione e dati da un backup:

```bash
sudo systemctl stop shinra
sudo tar -xzf /var/backups/shinra/shinra-AAAAMMGG-HHMMSS.tar.gz -C /opt/Shinra
sudo chown -R shinra:shinra /opt/Shinra/config /opt/Shinra/data
sudo systemctl start shinra
```

---

## Cosa resta da fare

- **Endpoint `/health` dedicato**, pubblico e senza informazioni sensibili.
  Oggi lo script interroga `/api/status`, che dalla v0.1.0 sara' autenticato:
  la verifica accetta quindi qualsiasi risposta HTTP, `401` compreso, perche'
  cio' che conta e' che il processo risponda. Funziona, ma un endpoint fatto
  apposta e' piu' onesto. Aggiunto alla issue #08.
- **Distribuzione con Docker e add-on per Home Assistant OS**: issue #37,
  milestone v0.5.0. A quel punto l'aggiornamento diventa il cambio di un tag
  d'immagine e questo documento diventa la procedura alternativa.
