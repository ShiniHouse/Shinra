# 🏡 Shinra — Assistente Domestico Intelligente & Hub Vocale IA

**Shinra** è un hub domotico avanzato con intelligenza artificiale locale (**Ollama**) e controllo integrato di **Home Assistant**, dotato di **sintesi vocale neurale ad alta definizione (Edge-TTS)** e compatibilità nativa con **Amazon Alexa / Echo**, **Google Home** e browser web.

Il nome *Shinra* nasce dall'unione concettuale con **Shinigami** (死神 — entità che osserva e supervisiona) e rappresenta una presenza discreta, intelligente e sempre pronta a gestire l'intera casa.

---

## 🌟 Indice dei Contenuti
- [✨ Funzionalità Principali](#-funzionalità-principali)
- [🏗️ Architettura del Sistema](#️-architettura-del-sistema)
- [📦 Installazione & Configurazione su Server Debian/Linux](#-installazione--configurazione-su-server-debianlinux)
- [🎙️ Motore Vocale & Voci Neurali HD](#️-motore-vocale--voci-neurali-hd)
- [📡 Guida Integrazione Amazon Alexa (Echo)](#-guida-integrazione-amazon-alexa-echo)
- [🌐 Configurazione Nginx Proxy Manager & Cloudflare](#-configurazione-nginx-proxy-manager--cloudflare)
- [⚙️ Parametri di Configurazione (`config/config.yaml`)](#️-parametri-di-configurazione-configconfigyaml)
- [🛠️ Risoluzione Problemi (Troubleshooting)](#️-risoluzione-problemi-troubleshooting)

---

## ✨ Funzionalità Principali

### 🧠 1. Cervello IA Locale (Zero Cloud per i Dati Privati)
* Elaborazione locale tramite **Ollama** su CPU o GPU con supporto ai migliori modelli compatti:
  * **`qwen2.5:3b`** *(Consigliato per velocità istantanea < 2s su CPU e supporto nativo ai Tool)*.
  * **`gemma3:4b`**, **`llama3.2:3b`**, **`qwen2.5:7b`**.
* **Zero Timeout & Routing Proattivo**: Risposte immediate in 1-2 frasi calibrate appositamente per la sintesi vocale.

### 🏠 2. Controllo Domotico Completo (Home Assistant)
* Scoperta automatica di entità, luci, interruttori, prese, termostati e sensori.
* **Mappa Dispositivi Interattiva**: Elenco dispositivi con badge stato, stanze e interruttori toggle rapidi.
* **Alias Personalizzati**: Assegna nomi naturali (es. *"Luce scrivania"* ➔ `light.yeelight_desk`).
* **Modalità & Routine Casa**: Attivazione di scenari multipli (es. *Modalità Cinema*, *Modalità Notte*, *Uscita Casa*).

### 🎙️ 3. Motore Vocale Neurale HD (Server-Side)
* Voci neurali ultra-realistiche in streaming MP3 via **Edge-TTS**:
  * 👨 **`Diego`** (Maschile / Stile *Jarvis HD* caldo e naturale).
  * 👩 **`Elsa`** (Femminile / Stile *Shinra HD* brillante ed espressivo).
  * 👩 **`Isabella`** (Femminile dolce e conversazionale).
  * 👨 **`Giuseppe`** (Maschile formale e istituzionale).
* Fallback automatico su **Web Speech API** del browser con controlli di Pitch (tonalità) e Rate (velocità).

### 🌦️ 4. Servizi in Tempo Reale & Cultura
* **Meteo Live**: Previsioni accurate per oggi e domani basate su Open-Meteo.
* **Fonti & Notizie RSS**: Oltre 20 canali preconfigurati (ANSA, Corriere, Repubblica, Il Sole 24 Ore, Tom's Hardware, HDBlog, ecc.).
* **Wikipedia IT**: Spiegazioni e definizioni enciclopediche immediate senza fronzoli.

### 👥 5. Gestione Utenti Multi-Profilo & Conoscenza Domestica
* Profili personalizzati con fasce d'età (*Adulto*, *Ragazzo*, *Bambino*) e calibrazione automatica del linguaggio.
* Schede strutturate per la memoria domestica (*Wi-Fi ospiti, orari raccolta rifiuti, codici allarme, preferenze*).

---

## 🏗️ Architettura del Sistema

```text
[ Browser Web / App Mobile ]        [ Dispositivi Amazon Echo ]
              \                                   /
               \                                 / (HTTPS /api/alexa)
                ▼                               ▼
       [ Cloudflare Edge (SSL + WAF Rule) ]
                        │
                        ▼
       [ Nginx Proxy Manager (Port 80/443) ]
                        │
                        ▼
       [ Shinra Backend (FastAPI :8000) ]
        ├── Intent Router & Tool Agent
        ├── Edge-TTS Server Engine (MP3 Stream)
        ├── Home Assistant Connector (:8123)
        └── Ollama LLM Connector (:11434 - qwen2.5:3b)
```

---

## 📦 Installazione & Configurazione su Server Debian/Linux

### 1. Clonazione e Setup Virtualenv
```bash
cd /opt
git clone https://github.com/ShiniHouse/Shinra.git
cd Shinra

# Creazione ambiente virtuale Python 3.10+
python3 -m venv .venv
source .venv/bin/activate

# Installazione dipendenze (FastAPI, Edge-TTS, Uvicorn, PyYAML, ecc.)
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Installazione e Download Modello Ollama
```bash
# Scarica il modello consigliato ad alta velocità
ollama pull qwen2.5:3b
```

### 3. Configurazione Servizio di Sistema (`systemd`)
Crea il file `/etc/systemd/system/shinra.service`:
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

Abilita e avvia il servizio:
```bash
systemctl daemon-reload
systemctl enable --now shinra
systemctl status shinra
```

---

## 📡 Guida Integrazione Amazon Alexa (Echo)

### 1. Crea la Skill su Amazon Developer Console
1. Accedi a **[developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask)** con lo stesso account Amazon dei tuoi Echo.
2. Clicca su **"Create Skill"**:
   * **Skill Name**: `Shinra`
   * **Primary Locale**: `Italian (IT)`
   * **Model**: `Custom`
   * **Hosting**: `Provision your own`
3. Seleziona **"Start from Scratch"** e conferma.

### 2. Interaction Model (JSON Editor)
Nel menu a sinistra vai su **Interaction Model** ➔ **JSON Editor** e incolla questo schema:

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "shinra",
      "intents": [
        {
          "name": "AMAZON.CancelIntent",
          "samples": []
        },
        {
          "name": "AMAZON.HelpIntent",
          "samples": []
        },
        {
          "name": "AMAZON.StopIntent",
          "samples": []
        },
        {
          "name": "AMAZON.NavigateHomeIntent",
          "samples": []
        },
        {
          "name": "AMAZON.FallbackIntent",
          "samples": []
        },
        {
          "name": "GeneralQueryIntent",
          "slots": [
            {
              "name": "query",
              "type": "AMAZON.SearchQuery"
            }
          ],
          "samples": [
            "dimmi {query}",
            "chiedi {query}",
            "fai {query}",
            "esegui {query}",
            "cosa {query}",
            "come {query}",
            "imposta {query}",
            "accendi {query}",
            "spegni {query}",
            "cerca {query}",
            "spiegami {query}",
            "fammi {query}",
            "apri {query}",
            "chiudi {query}",
            "domanda {query}"
          ]
        }
      ],
      "types": []
    }
  }
}
```
Clicca su **"Save Model"** e poi su **"Build Model"**.

### 3. Configurazione Endpoint
1. Clicca su **Endpoint** (a sinistra).
2. Seleziona **HTTPS**.
3. Inserisci nei campi **Default Region** e **Europe and India**:
   ```text
   https://shinra.guidelli.net/api/alexa
   ```
4. Seleziona come certificato SSL:
   * **`My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority`**
5. Clicca **"Save Endpoints"**.

### 4. Come Usare Shinra con Alexa
* **Comandi Diretti One-Shot**:
  * *"Alexa, chiedi a Shinra che tempo farà domani ad Arezzo"*
  * *"Alexa, dì a Shinra di spegnere la luce in cucina"*
  * *"Alexa, chiedi a Shinra le ultime notizie"*
* **Sessione Continua**:
  * *"Alexa, apri Shinra"* ➔ *"Shinra online. Con chi parlo?"* ➔ *"Alessio"* ➔ *"Alessio, dimmi."*
* **Routine Rapida**:
  * Nell'app Alexa crea una Routine con attivazione vocale *"Shinra"* e azione personalizzata *"apri Shinra"*. Ti basterà dire: **`"Alexa, Shinra"`**!

---

## 🌐 Configurazione Nginx Proxy Manager & Cloudflare

### Nginx Proxy Manager (NPM)
* **Domain Names**: `shinra.guidelli.net`
* **Forward Hostname / IP**: `10.10.1.248`
* **Forward Port**: `8000`
* **Block Common Exploits**: ⚠️ **Disattivare** (permette ai server di Alexa di comunicare senza blocchi 403).
* **SSL**: `Force SSL` attivo, `HTTP/2 Support` attivo.
* **Advanced (Custom Nginx Configuration)**:
  ```nginx
  proxy_read_timeout 180s;
  proxy_connect_timeout 180s;
  proxy_send_timeout 180s;
  ```

### Cloudflare WAF Rule (per Alexa)
Nel pannello di Cloudflare (*Security → WAF → Custom Rules*):
* **Field**: `URI Path` equals `/api/alexa`
* **Action**: `Skip` (Salta WAF, Bot Fight Mode e controlli di sicurezza per le richieste Alexa).

---

## ⚙️ Parametri di Configurazione (`config/config.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8000

assistant:
  name: "Shinra"
  default_city: "Roma"

llm:
  provider: "ollama"
  base_url: "http://localhost:11434"
  model: "qwen2.5:3b"
  temperature: 0.3
  max_tokens: 150

home_assistant:
  enabled: true
  url: "http://10.10.1.252:8123"
  token: "TUO_LONG_LIVED_ACCESS_TOKEN"

voice:
  default_gender: "male"  # male / female
  neural_voice: "it-IT-DiegoNeural"
```

---

## 🛠️ Risoluzione Problemi (Troubleshooting)

| Problema | Causa Possibile | Soluzione |
| :--- | :--- | :--- |
| **Errore 524 Timeout su Cloudflare** | Modello LLM troppo lento o prompt pesante su CPU | Usa `qwen2.5:3b` con `max_tokens: 150`. Lo schema dei tool complessi viene caricato solo se necessario. |
| **Alexa: "Non posso raggiungere la skill"** | Cloudflare WAF o NPM bloccano le chiamate AWS | Disattiva *Block Common Exploits* in NPM e crea la regola di bypass WAF su Cloudflare per `/api/alexa`. |
| **Voci Web Speech robotiche** | Voci di sistema base del browser | Usa le **Voci Neurali Server HD** (*Diego / Elsa*) dal selettore vocale di Shinra. |
| **Microfono non si avvia su Chrome/Safari** | Connessione HTTP non sicura | Assicurati di accedere sempre via **HTTPS** (`https://shinra.guidelli.net`). |

---

## 📄 Licenza
Rilasciato sotto licenza MIT. Sviluppato con passione per l'automazione domestica intelligente e privata.
