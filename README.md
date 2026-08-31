# 🏡 Shinra — Assistente Domestico Intelligente (Gemma + Ollama + Home Assistant)

**Shinra** è un hub intelligente per l'assistenza domestica e vocale alimentato da modelli LLM locali (**Gemma tramite Ollama**), integrato con **Home Assistant** e compatibile con i dispositivi **Amazon Alexa / Echo** e **Google Home**.

Il nome *Shinra* nasce da **Shinigami** (死神 — divinità della morte nella cultura giapponese e nei manga) e dall'idea di un'entità che governa e supervisiona l'ambiente domestico con intelligenza e discrezione.

---

## ✨ Funzionalità Principali

- 🧠 **Cervello IA Locale (Gemma su Ollama)**: Elaborazione sicura e privata direttamente sul tuo computer.
- 🏠 **Controllo Domotico Completo (Home Assistant)**: Gestione di luci, prese, termostati, climatizzazione, tapparelle e scene domotiche.
- 🌤️ **Meteo in Tempo Reale**: Previsioni accurate per qualsiasi città (basato su Open-Meteo, senza API key).
- 📰 **Notizie dal Mondo & Attualità**: Aggiornamenti in tempo reale su leggi, politica, economia e fatti del mondo.
- 📚 **Cultura Generale & Definizioni**: Wikipedia integrata per spiegazioni storiche e scientifiche.
- 🗣️ **Interfaccia Vocale & Web Dashboard**: Pannello web con microfono (Web Speech API) e sintesi vocale.
- 📡 **Integrazione Amazon Alexa**: Endpoint nativo per Alexa Skill Kit — evoca Shinra con *"Alexa, apri Shinra"*.

---

## 🚀 Avvio Rapido

### 1. Avviare il server
```powershell
.\.venv\Scripts\python.exe run.py
```
Apri la dashboard: **`http://localhost:8000`**

### 2. Configurazione (`config/config.yaml`)
- **`llm.model`**: modello Gemma installato in Ollama (es. `gemma2:9b`).
- **`home_assistant.url`**: indirizzo di Home Assistant (es. `http://homeassistant.local:8123`).
- **`home_assistant.token`**: *Long-Lived Access Token* generabile in Home Assistant (*Profilo → Sicurezza → Token*).

---

## 🎙️ Configurazione Alexa Skill
Per collegare i tuoi Echo e parlare con Shinra dalla voce:
👉 **[ALEXA_SETUP_GUIDE.md](ALEXA_SETUP_GUIDE.md)**

---

## 🛠️ Struttura del Progetto
```
Shinra/
├── config/
│   ├── config.yaml          # Parametri server, Ollama, HA, Alexa
│   ├── settings.py          # Gestore impostazioni
│   └── prompt_templates.py  # Personalità e istruzioni per Shinra (Gemma)
├── core/
│   ├── agent.py             # Agente centrale & ciclo Tool Calling
│   ├── ollama_client.py     # Connettore Ollama asincrono
│   ├── ha_client.py         # Connettore Home Assistant
│   ├── memory.py            # Cronologia conversazione
│   └── tools/
│       ├── registry.py      # Registro e schemi tool calling
│       ├── ha_tools.py      # Controllo dispositivi Home Assistant
│       ├── weather.py       # Previsioni meteo (Open-Meteo)
│       ├── news_search.py   # Notizie ANSA RSS & Google News
│       ├── wikipedia_tool.py# Enciclopedia Wikipedia IT
│       └── reminders.py     # Promemoria e note
├── integrations/
│   └── alexa/
│       └── skill_handler.py # Handler richieste Alexa Skill Kit
├── server/
│   └── app.py               # Server FastAPI
├── web/
│   └── templates/
│       └── index.html       # Dashboard Web con voce e log in tempo reale
├── run.py                   # Script di avvio
└── requirements.txt
```
