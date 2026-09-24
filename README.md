# 🏡 Shinra — Assistente Domestico Intelligente & Hub Vocale IA

**Shinra** è un hub domotico avanzato con intelligenza artificiale locale (**Ollama**) e controllo integrato di **Home Assistant**, dotato di **sintesi vocale neurale ad alta definizione (Edge-TTS)**, **editor di routine visuale a grafo 2D (stile Visio / Node-RED)**, supporto **PWA Mobile** e compatibilità nativa con **Amazon Alexa / Echo**, **Google Home** e browser web.

Il nome *Shinra* nasce dall'unione concettuale con **Shinigami** (死神 — entità che osserva e supervisiona) e rappresenta una presenza discreta, intelligente e sempre pronta a gestire l'intera casa in modo privato e sicuro.

---

## 🚧 Stato del progetto — beta, in lavorazione verso la `0.5.0`

Shinra è in **beta** e procede per fasi verso la `1.0.0`. Ogni versione minor
corrisponde a una fase della roadmap ed è installabile e utilizzabile; fino
alla `1.0.0` una minor può introdurre modifiche incompatibili.

**L'ultima release è la `0.4.0`**: la casa smette di aspettare la domanda.
Le routine partono da sole — a un orario, all'alba, su una soglia — quello che
dici al microfono della dashboard resta in casa, e la casa sa da quale stanza
le stai parlando. Più passkey al posto del PIN, notifiche push, e identità sul
canale vocale.

Due cose che quella release **non** dichiara risolte, e le dice: da un Echo
l'audio va ad Amazon per costruzione, e nessuno ha ancora guardato una regola
scattare in una casa vera.

Note complete: [`docs/release/v0.4.0.md`](docs/release/v0.4.0.md).

**La `0.5.0` è in lavorazione** — prodotto: quello che serve perché Shinra lo
installi qualcuno che non sei tu. Quello che è già dentro il ramo principale:

- **L'interfaccia rifatta** (#123–#128, #134, #139): da otto ingressi a tre,
  impostazioni a sezioni, e la colonna di destra che racconta cosa sta per
  succedere in casa invece della diagnostica.
- **Il frontend scomposto** (#144–#151, #176): `index.html` è passato da 7.438
  righe a **160**; il markup delle schede sta in nove file inclusi, il
  JavaScript in ventitré file, uno per area, il più lungo di **460** righe; il
  CSS in cinque; ESLint e Prettier girano in CI. Nessun file del frontend
  supera le cinquecento righe, ed è un test a dirlo. E lo stato che attraversa
  le aree — undici variabili, una girava per cinque file — sta in un
  contenitore solo (#177). E ogni
  valore che finisce nella pagina viene scappato: prima bastava un dispositivo
  chiamato `<img onerror=...>` in Home Assistant.
- **I gesti dell'editor a nodi in CI** (#156): sette gesti veri, con un
  browser vero, perché un test che legge il sorgente non sa se un clic arriva
  o se se lo mangia un antenato.
- **Lo spegnimento** (#118): il servizio si ferma in pochi secondi invece di
  aspettare il SIGKILL di systemd dopo novanta.
- **Backup e ripristino** (#35): un archivio con tutto quello che serve a
  rimettere in piedi la casa, la versione dello schema scritta dentro, la
  rotazione delle copie vecchie e un backup automatico a orario. I PIN non
  escono mai in chiaro — `scripts/esporta_json.py` li scriveva su disco.
- **La distribuzione** (#37, in parte): immagine Docker a due stadi che gira
  come utente non privilegiato, `docker-compose.yml`, e la pubblicazione su
  GHCR per `amd64` e `arm64` a ogni tag. Resta l'add-on per Home Assistant OS.
- **L'installazione verificata** (#38, in parte): la CI costruisce l'immagine,
  la avvia e controlla di riuscire davvero a entrare. È così che si è scoperto
  che l'immagine partiva senza `data/examples/`: rispondeva 200 e nessuno
  poteva accedere.
- **La dashboard che dice cosa sta succedendo** (#152, #153, #159, #161): il
  canale degli eventi accetta i dispositivi fidati invece di rifiutarli dopo
  ogni riavvio, una sessione scaduta viene detta invece di ritentare in
  silenzio all'infinito, una scheda che non esiste torna alla console invece
  di lasciare la pagina vuota, e il tema si applica prima del primo disegno.
- **L'intervista che impara** (#170, in parte): quando il modello non capisce
  lo dice, invece di rispondere «Ricevuto! Ho aggiunto 1 nuovi dettagli»; e
  prima di salvare fa vedere cosa ha capito, così un'interpretazione sbagliata
  non diventa conoscenza permanente in silenzio.

Restano la parola di attivazione, i moduli ES veri con lo stato in un posto
solo, l'internazionalizzazione, l'add-on per Home Assistant OS e il resto
della documentazione utente. Il quadro completo è nella
[ROADMAP](docs/ROADMAP.md).

| Documento | Cosa contiene |
| :--- | :--- |
| [`docs/PRIMI-PASSI.md`](docs/PRIMI-PASSI.md) | Dal primo accesso alla prima automazione: profili, Home Assistant, alias, routine |
| [`docs/PROBLEMI.md`](docs/PROBLEMI.md) | Cosa fare quando qualcosa non funziona, guasto per guasto — tutti successi davvero |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Le cinque fasi da `0.1.0` a `1.0.0` e i criteri di uscita di ciascuna |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Struttura attuale, struttura target e come si aggiunge un modulo nuovo |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Aggiornamento del server Debian e cosa fare se non si riesce più a entrare |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Flusso di lavoro, convenzioni sui commit, processo di rilascio |
| [`SECURITY.md`](SECURITY.md) | Difetti di sicurezza noti e come segnalarne di nuovi |
| [`docs/backlog/`](docs/backlog/) | Il piano di lavoro completo, issue per issue |

> ### ⚠️ Aggiornando dalla versione precedente
>
> - **L'autenticazione è attiva per difetto.** Al primo avvio, se nessun profilo
>   ha un PIN, ne viene generato uno e scritto nel log una volta sola:
>   `journalctl -u shinra --no-pager | grep "PRIMO ACCESSO"`. Se è già scorso
>   via, si reimposta con `scripts/imposta_pin.py`.
> - **L'endpoint Alexa richiede `SHINRA_ALEXA_SKILL_ID` in `.env`**: senza,
>   rifiuta ogni richiesta.
> - I segreti rimasti in `config/config.yaml` vengono spostati in `.env` al
>   primo avvio e cancellati da lì.

---

## 📸 Anteprima Dashboard

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="La console vocale di Shinra: chat con l'assistente a sinistra, timer e prossimi scatti a destra" width="100%">
</p>

<p align="center"><sub>La console vocale sulla <code>0.5.0</code> in lavorazione, dopo la scomposizione del frontend.</sub></p>

---

## 🌟 Indice dei Contenuti
- [✨ Funzionalità Principali](#-funzionalità-principali)
- [🏗️ Architettura del Sistema](#️-architettura-del-sistema)
- [🐳 Installazione con Docker](#-installazione-con-docker)
- [📦 Installazione & Configurazione su Server Linux/Debian](#-installazione--configurazione-su-server-linuxdebian)
- [🎛️ Canvas Visuale a Nodi per Routine (Visio Style)](#️-canvas-visuale-a-nodi-per-routine-visio-style)
- [⏰ Timer & Promemoria Vocali Live](#-timer--promemoria-vocali-live)
- [📱 Installazione PWA (Smartphone iOS & Android)](#-installazione-pwa-smartphone-ios--android)
- [🎙️ Motore Vocale & Voci Neurali HD](#️-motore-vocale--voci-neurali-hd)
- [📡 Guida Integrazione Amazon Alexa (Echo)](#-guida-integrazione-amazon-alexa-echo)
- [🌐 Configurazione Nginx Reverse Proxy & SSL](#-configurazione-nginx-reverse-proxy--ssl)
- [⚙️ Parametri di Configurazione (`config/config.yaml`)](#️-parametri-di-configurazione-configconfigyaml)
- [🛠️ Risoluzione Problemi (Troubleshooting)](#️-risoluzione-problemi-troubleshooting)

---

## 🔒 Cosa resta in casa, e cosa no

Questo elenco esisteva prima solo come slogan — *«Zero Cloud per i Dati
Privati»*, *«100% privata»* — e non era vero: fino alla `0.4.0` **ogni parola
detta al microfono della dashboard veniva inviata a Google**, perché il
riconoscimento vocale usava la Web Speech API del browser. Adesso non succede
più, e questa tabella dice esattamente come stanno le cose invece di
riassumerle in uno slogan.

| Cosa | Dove va | Nota |
| :--- | :--- | :--- |
| Il modello che risponde | **Resta in casa** | Ollama, sul tuo server |
| La conoscenza di casa e le sue ricerche | **Resta in casa** | Anche gli embedding: li calcola Ollama |
| Comandi ai dispositivi | **Resta in casa** | Home Assistant sulla tua rete |
| Anagrafica, PIN, passkey, registro delle azioni | **Resta in casa** | Sul disco del server |
| **La voce che parli al microfono** | **Resta in casa** *(dalla `0.4.0`)* | Whisper sul server. Vedi sotto |
| Il testo delle risposte lette a voce | **Esce** → Microsoft | Edge-TTS. Si può spegnere e usare le voci del browser |
| Meteo | **Esce** → Open-Meteo | La tua città, non chi sei |
| Notizie | **Esce** → le fonti RSS configurate | |
| Comandi detti a un Echo | **Esce** → Amazon | È un dispositivo Amazon: l'audio lo elabora Amazon, sempre |
| Notifiche push | **Esce** → Google/Mozilla/Apple | Il contenuto è **cifrato**: instradano una busta che non possono leggere |

Niente di ciò che esce porta con sé un elenco dei tuoi dispositivi, il
contenuto della tua conoscenza di casa o chi sei.

### La voce, in dettaglio

Il microfono della dashboard registra e manda l'audio al **tuo** server, che
lo trascrive con [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
Non è installato per difetto — pesa, e il modello si scarica al primo uso —
quindi va aggiunto:

```bash
sudo -u shinra /opt/Shinra/.venv/bin/pip install "faster-whisper>=1.0"
sudo systemctl restart shinra
```

**Finché non lo installi il microfono della dashboard non funziona, e lo
dice.** È voluto: l'alternativa sarebbe ripiegare in silenzio sulla Web Speech
API, cioè rimettere il problema esattamente dov'era. Nel frattempo si scrive
con la tastiera, e tutto il resto funziona.

Chi preferisce la velocità del browser alla privacy può sceglierlo
esplicitamente, mettendo in `config/config.yaml`:

```yaml
voce:
  motore: browser   # l'audio esce di casa e va a Google/Apple
```

---

## ✨ Funzionalità Principali

### 🧠 1. Cervello IA Locale
* Elaborazione locale tramite **Ollama** su CPU o GPU con supporto a qualsiasi modello LLM:
  * **`qwen2.5:3b`** *(Consigliato per velocità istantanea < 1s su CPU e supporto nativo ai Tool)*.
  * **`gemma2:9b`**, **`llama3.2:3b`**, **`qwen2.5:7b`**.
* **Fast-Path Istantaneo (< 0.05s)**: Risposte istantanee per meteo, notizie, orologio, timer, controllo luci e scenari senza attendere l'inferenza completa del modello quando non necessaria.

### 🏠 2. Controllo Domotico Completo (Home Assistant)
* Scoperta automatica di entità, luci, interruttori, prese, termostati, climatizzatori e sensori.
* **Mappa Dispositivi Interattiva**: Elenco dispositivi raggruppati per stanze con interruttori toggle rapidi.
* **Alias Personalizzati**: Assegna nomi naturali in linguaggio parlato (es. *"Luce scrivania"* ➔ `light.yeelight_desk`).

### 🎛️ 3. Canvas Visuale a Nodi per Routine (Stile Visio / Node-RED)
* Editor 2D a schermo intero con nodi trascinabili e cavi di collegamento Bézier interattivi:
  * ⚡ **Innesco Vocale (Trigger):** Frasi multiple di attivazione (*"Modalità Cinema"*, *"Vado a dormire"*).
  * 💡 **Dispositivo Home Assistant:** Accensione, spegnimento o regolazione di qualsiasi entità o alias.
  * ⏱️ **Ritardo Temporizzato (Pausa):** Attesa programmata tra un'azione e l'altra (es. 5s, 10s, 30s).
  * 🗣️ **Annuncio Vocale (TTS):** Risposta personalizzata di Shinra con voce neurale.
* **Simulatore con Flusso Luminoso in Tempo Reale**: I cavi si illuminano con impulsi animati per testare la sequenza visivamente prima di salvarla.

### ⏰ 4. Timer & Promemoria Vocali con Countdown Live
* Impostazione immediata a voce: *"Shinra, metti un timer di 9 minuti per la pasta"*, *"Ricordami di prendere le medicine alle 17:30"*.
* Widget dedicato nella console web con avanzamento al secondo e riproduzione di **chime sonoro elettronico + annuncio vocale** allo scadere.

### 📱 5. Progressive Web App (PWA) per Smartphone
* Web App installabile a schermo intero su iPhone (Safari ➔ *Aggiungi a Home*) e Android (*Installa App*).
* Tema scuro Cyberpunk, cache con Service Worker e pulsante di installazione rapida.

### 🎙️ 6. Motore Vocale Neurale HD (Server-Side)
* Voci neurali ultra-realistiche in streaming MP3 via **Edge-TTS**:
  * 👨 **`Diego`** (Maschile / Stile *Jarvis HD* caldo e naturale).
  * 👩 **`Elsa`** (Femminile / Stile *Shinra HD* brillante ed espressivo).
  * 👩 **`Isabella`** (Femminile dolce e conversazionale).
  * 👨 **`Giuseppe`** (Maschile formale e istituzionale).
* Fallback automatico su **Web Speech API** del browser con controlli di Pitch (tonalità) e Rate (velocità).
* Il testo da leggere esce verso Microsoft: è l'ultimo servizio esterno che
  resta nel percorso vocale, e si spegne scegliendo le voci del browser.

### 🎧 7. Riconoscimento Vocale in Casa
* Il microfono della dashboard registra e manda l'audio al **tuo** server, che
  lo trascrive con **faster-whisper**. Non esce niente.
* Modello configurabile da `tiny` a `large-v3`: su una CPU di un piccolo
  server `base` è il compromesso che regge — `small` raddoppia l'attesa,
  `tiny` sbaglia i nomi propri, che in una casa sono quasi tutto.
* Le frasi che Whisper inventa sul silenzio — *«Sottotitoli e revisione a cura
  di…»* — vengono scartate invece di essere eseguite come comandi.
* Va installato a parte (`pip install faster-whisper`): vedi
  [Cosa resta in casa, e cosa no](#-cosa-resta-in-casa-e-cosa-no).

---

## 🏗️ Architettura del Sistema

```text
[ Browser Web / PWA Mobile ]        [ Dispositivi Amazon Echo ]
              \                                   /
               \                                 / (HTTPS /api/alexa)
                ▼                               ▼
       [ Cloudflare Edge (SSL / WAF Rule) ]
                        │
                        ▼
       [ Nginx Reverse Proxy (Port 80/443) ]
                        │
                        ▼
       [ Shinra Backend (FastAPI :8000) ]
        ├── Intent Router & Tool Agent
        ├── Timer & Reminder Engine
        ├── Edge-TTS Server Engine (MP3 Stream)
        ├── Home Assistant Connector (:8123)
        └── Ollama LLM Connector (:11434 - qwen2.5:3b)
```

---

## 🐳 Installazione con Docker

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

## 📦 Installazione & Configurazione su Server Linux/Debian

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

## 📡 Guida Integrazione Amazon Alexa (Echo)

Per la guida completa dettagliata alla creazione della Skill, consulta il file dedicato: **[ALEXA_SETUP_GUIDE.md](ALEXA_SETUP_GUIDE.md)**.

### Riepilogo Rapido:
1. Accedi a **[developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask)** e crea una Skill Custom denominata `Shinra`.
2. Incolla l'Interaction Model da `ALEXA_SETUP_GUIDE.md` nella sezione **JSON Editor**.
3. Configura l'endpoint HTTPS: `https://tuodominio.com/api/alexa`.
4. Seleziona il certificato SSL Wildcard e clicca su **Build Model**.

---

## 🌐 Configurazione Nginx Reverse Proxy & SSL

### Esempio Configurazione Nginx / Nginx Proxy Manager:
* **Domain Name**: `tuodominio.com` o `shinra.tuodominio.com`
* **Forward IP / Hostname**: `192.168.1.100` (IP locale del server Shinra)
* **Forward Port**: `8000`
* **Block Common Exploits**: **lasciare attivo**. Nelle versioni precedenti questa
  guida diceva di disattivarlo per far passare Alexa: era un consiglio sbagliato,
  perché toglieva una protezione a tutto il sito. Da `v0.1.0` l'endpoint `/api/alexa`
  verifica da sé la firma Amazon, quindi non serve abbassare nulla a monte.
  Se le chiamate di Alexa venissero comunque bloccate, restringi l'eccezione al solo
  percorso `/api/alexa` invece di disattivare il controllo ovunque.
* **SSL**: `Force SSL` attivo, `HTTP/2 Support` attivo.

```nginx
server {
    listen 443 ssl http2;
    server_name shinra.tuodominio.com;

    # Certificati SSL
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 180s;
        proxy_connect_timeout 180s;
        proxy_send_timeout 180s;
    }
}
```

### Regola Cloudflare WAF (solo se necessaria)

Da `v0.1.0` **non serve più** una regola di bypass: `/api/alexa` verifica la
firma di Amazon, l'`applicationId` della skill e l'età della richiesta, e
rifiuta tutto il resto con un `400`.

Se Cloudflare bloccasse comunque le chiamate di Amazon, in
*Security → WAF → Custom Rules* limita l'eccezione al minimo indispensabile:

* **Field**: `URI Path` equals `/api/alexa`
* **Action**: `Skip` — e **solo** le regole che stanno effettivamente bloccando,
  non l'intero WAF e non Bot Fight Mode su tutto il dominio.

---

## ⚙️ Parametri di Configurazione (`config/config.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8000

llm:
  ollama_url: "http://localhost:11434"   # o SHINRA_OLLAMA_URL
  model: "qwen2.5:3b"
  temperature: 0.4
  max_tokens: 150

home_assistant:
  enabled: true
  url: "http://homeassistant.local:8123" # o SHINRA_HA_URL
  # Il token NON si mette qui: va in .env come SHINRA_HA_TOKEN

assistant:
  name: "Kyra"                           # come si chiama quando le parli
  default_city: "Roma"

voce:
  motore: "locale"                       # locale | browser
  modello: "base"
  lingua: "it"

security:
  auth_enabled: true

salvataggio:
  abilitato: true
  ogni_ore: 24.0
  da_conservare: 14
```

Questo è un estratto: `config/config.example.yaml` è il riferimento completo,
con il perché di ogni scelta accanto a ciascuna voce. I nomi qui sopra sono
quelli veri — `test_il_readme_documenta_chiavi_che_esistono` fallisce se uno
di loro smette di esserlo.

**I segreti non stanno in `config.yaml`.** Token, PIN amministratore e segreto
di sessione vivono in `.env` o nell'ambiente; se ne trova uno nel file di
configurazione, al primo avvio viene spostato e cancellato da lì. Il motivo è
che `config.yaml` è finito in un commit una volta, e basta una volta.

---

## 🛠️ Risoluzione Problemi (Troubleshooting)

I quattro qui sotto sono quelli che si incontrano più spesso. L'elenco
completo — un guasto per voce, tutti successi davvero, con il sintomo per
come si presenta e non per come lo si racconterebbe dopo — sta in
[`docs/PROBLEMI.md`](docs/PROBLEMI.md).

| Problema | Causa Possibile | Soluzione |
| :--- | :--- | :--- |
| **Errore 524 Timeout su Cloudflare / Proxy** | Modello LLM troppo pesante per la CPU | Usa `qwen2.5:3b` o un modello quantizzato veloce per rispondere in meno di 1 secondo. |
| **Alexa: "Non posso raggiungere la skill"** | Manca `SHINRA_ALEXA_SKILL_ID`, oppure il proxy blocca le chiamate AWS | Verifica prima il log: `journalctl -u shinra \| grep Alexa` dice il motivo esatto del rifiuto. Se manca l'App ID, impostalo in `.env`. Solo se il problema è il proxy, restringi l'eccezione al percorso `/api/alexa`. |
| **Voci Web Speech robotiche** | Voci di default del browser | Seleziona le **Voci Neurali Server HD** (*Diego / Elsa*) dal selettore vocale di Shinra. |
| **Microfono non si avvia su Chrome/Safari** | Connessione HTTP non sicura | Assicurati di accedere sempre via **HTTPS** (`https://tuodominio.com`). |

---

## 📄 Licenza
Rilasciato sotto licenza MIT. Sviluppato per un'automazione domestica
intelligente ed elegante, che tiene in casa ciò che può tenere in casa e dice
apertamente il resto: vedi [Cosa resta in casa, e cosa
no](#-cosa-resta-in-casa-e-cosa-no).
