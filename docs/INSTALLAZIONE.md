# Installazione

Shinra si installa in due modi, e si aggiorna in uno solo. Questa pagina e' la
procedura completa; il [README](../README.md) ha solo la versione corta.

| Strada | Quando conviene | Cosa serve |
| :--- | :--- | :--- |
| [**Docker**](#con-docker) | Quasi sempre. Nessun ambiente virtuale, nessun `systemd`, aggiornamento in una riga | Docker con il plugin Compose |
| [**A mano**](#a-mano-su-linuxdebian) | Quando vuoi il servizio gestito da `systemd` senza container, o stai sviluppando | Python 3.10+, `git`, `python3-venv` |
| **Add-on per Home Assistant OS** | **Non esiste ancora.** Vedi [sotto](#home-assistant-os-ladd-on-non-ce-ancora) per cosa fare nel frattempo | — |

In tutti e due i casi servono **Ollama** (il modello che risponde) e, se vuoi
comandare la casa, un'istanza di **Home Assistant** raggiungibile dalla rete.
Senza Ollama e senza Home Assistant Shinra parte lo stesso e dice nel log cosa
manca, ma non risponde a niente di utile.

**Come capisci che ha funzionato:** la dashboard si apre su
`http://INDIRIZZO-DEL-SERVER:8000`, accedi con il PIN del primo accesso e la
chat risponde. Da li' la strada continua in [PRIMI-PASSI](PRIMI-PASSI.md);
se qualcosa non va, [PROBLEMI](PROBLEMI.md) e' scritta guasto per guasto.

---

## Con Docker

La strada piu' corta: nessun ambiente virtuale, nessun `systemd`, e
l'aggiornamento e' una riga.

```bash
mkdir shinra && cd shinra
curl -O https://raw.githubusercontent.com/ShiniHouse/Shinra/main/docker-compose.yml
docker compose up -d
```

Il PIN del primo accesso compare nel log, **una volta sola**:

```bash
docker compose logs shinra | grep "PRIMO ACCESSO"
```

Poi la dashboard su **`http://INDIRIZZO-DEL-SERVER:8000`**, e il modello, una
volta sola:

```bash
docker compose exec ollama ollama pull qwen2.5:3b
```

### Il token di Home Assistant

Home Assistant non sta nel compose: quasi sempre gira gia' da un'altra parte.
Il token si mette in un file `.env` accanto a `docker-compose.yml` — Compose
lo legge da solo — e **non** dentro l'immagine:

```bash
cat > .env <<'EOF'
SHINRA_HA_URL=http://homeassistant.local:8123
SHINRA_HA_TOKEN=il-tuo-token
EOF
chmod 600 .env
docker compose up -d
```

### Cosa sopravvive, e cosa no

Tre volumi con nome: `shinra-dati` (database, log, salvataggi automatici),
`shinra-configurazione` (`config.yaml`) e `ollama-modelli`. Un
`docker compose down` non li tocca; `docker compose down -v` li cancella —
e con loro tutta la casa.

Il salvataggio della configurazione funziona anche qui:

```bash
docker compose exec shinra python scripts/salvataggio.py salva
```

### Aggiornare

```bash
docker compose pull && docker compose up -d
```

Il database si migra da solo alla partenza.

### Home Assistant OS: l'add-on non c'e' ancora

Chi usa **Home Assistant OS** o **Supervised** si aspetterebbe un add-on da
installare con un clic. Non c'e', ed e' una scelta dichiarata: scriverlo senza
poterlo installare da nessuna parte vorrebbe dire consegnare qualcosa che
nessuno ha mai visto funzionare. Serve anche un lavoro sul frontend — sotto
l'ingress di Home Assistant i percorsi assoluti della dashboard si rompono
tutti — che appartiene alla issue #34.

Fino ad allora, anche su quelle installazioni Shinra si mette con Docker, qui
sopra, e si collega a Home Assistant col token come tutti gli altri.

---

## A mano, su Linux/Debian

> Questa procedura è stata **verificata da zero su una macchina pulita**
> seguendo solo quello che è scritto qui: clone, dipendenze, configurazione,
> primo avvio, primo accesso. Se un passaggio non funziona, è un difetto di
> questa pagina — [aprine una issue](https://github.com/ShiniHouse/Shinra/issues).

### 1. Quello che serve prima

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
```

Serve **Python 3.10 o più recente**: `python3 --version` lo dice.
Su Debian `python3-venv` è un pacchetto a parte e senza non si crea
l'ambiente virtuale — è il primo punto in cui ci si ferma.

### 2. Clonazione e ambiente virtuale
```bash
cd /opt
sudo git clone https://github.com/ShiniHouse/Shinra.git
cd Shinra

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e .
```

### 3. Configurazione iniziale
```bash
cp config/config.example.yaml config/config.yaml
nano config/config.yaml
```

Il file di esempio funziona così com'è: si può anche lasciarlo intatto al
primo giro e sistemarlo dopo, dalle impostazioni della dashboard.

**I segreti non vanno qui.** Il token di Home Assistant e gli altri si
mettono in `.env`, che non è versionato:

```bash
echo 'SHINRA_HA_TOKEN=il-tuo-token-di-home-assistant' >> .env
chmod 600 .env
```

Senza token Shinra parte lo stesso e lo dice nel log: la casa risponde, ma
non controlla niente.

**Il database non va preparato**: viene creato e migrato da solo al primo
avvio. Non c'è nessun comando da lanciare.

### 4. Ollama e il modello
Ollama è un programma a parte e va installato per primo, seguendo le
istruzioni ufficiali su [ollama.com](https://ollama.com/download). Deve
restare in ascolto su `localhost:11434`, che è dove Shinra lo cerca.

Poi il modello:
```bash
ollama pull qwen2.5:3b
```

È lo stesso che `config.example.yaml` configura per difetto, e non è una
preferenza: `qwen2.5:3b` supporta i **tool** in modo nativo, e qui i tool
sono tutto — accendere una luce, mettere un timer, leggere una scadenza.
Un modello senza tool risponde e non fa niente.

Senza Ollama, Shinra parte e funziona per tutto ciò che non passa dal
modello: timer, dispositivi, routine.

### 5. Primo avvio e primo accesso

```bash
.venv/bin/python run.py
```

Apri **`http://INDIRIZZO-DEL-SERVER:8000`** dal browser.

Troverai una schermata di accesso: **l'autenticazione è attiva per difetto**.
Al primo avvio viene creato un profilo *Amministratore* con un PIN generato
a caso, e quel PIN **compare una volta sola, nel log dell'avvio**:

```
=== PRIMO ACCESSO ===  PIN per Amministratore: 462783
```

Annotalo. Se è già scorso via, si reimposta con `python scripts/imposta_pin.py`.

### 6. Servizio di sistema (`systemd`)
Quando tutto funziona a mano, si mette in servizio. Crea
`/etc/systemd/system/shinra.service`:

```ini
[Unit]
Description=Shinra AI Smart Home Hub
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Shinra
ExecStart=/opt/Shinra/.venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now shinra
systemctl status shinra
```

Il PIN del primo accesso, se il primo avvio è avvenuto qui:
```bash
journalctl -u shinra --no-pager | grep "PRIMO ACCESSO"
```

### 7. Metti al sicuro la configurazione
Le ore che passerai a insegnare alla casa i nomi delle luci e le routine
valgono più del resto. Un archivio si scrive così:

```bash
.venv/bin/python scripts/salvataggio.py salva
```

Da lì in poi se ne scrive uno al giorno da solo, in `data/salvataggi/`.
Non contiene segreti: né il token, né i PIN. Copiane uno ogni tanto fuori
da questa macchina — un backup sullo stesso disco protegge dagli errori,
non dai dischi che muoiono.

---

## E dopo

- [Primi passi](PRIMI-PASSI.md): dal primo accesso alla prima automazione.
- [Aggiornare il server](DEPLOY.md): la procedura, e cosa fare se non si riesce piu' a entrare.
- [Alexa](../README.md#-guida-integrazione-amazon-alexa-echo) e il [reverse proxy](../README.md#-configurazione-nginx-reverse-proxy--ssl).
- [Quando qualcosa non funziona](PROBLEMI.md).
