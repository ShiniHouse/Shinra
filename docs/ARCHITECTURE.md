# Architettura

Questo documento descrive **com'e' fatto Shinra oggi**, **dove deve arrivare**
e — soprattutto — **la regola da seguire per aggiungere un modulo nuovo** senza
far crescere il debito.

---

## 1. Nomenclatura

Tre nomi diversi circolano nel progetto. Da qui in avanti valgono cosi':

| Nome | Cosa indica |
| :--- | :--- |
| **Shinra** | Il progetto e il repository. Non cambia. |
| **ShiniHouse** | L'organizzazione GitHub proprietaria del repository. |
| **Kyra** | Il nome predefinito dell'assistente, modificabile dall'utente nelle impostazioni. Non e' il nome del progetto. |

Il codice non deve mai scrivere a mano il nome dell'assistente: si legge sempre
da `settings.assistant.name`.

---

## 2. Struttura attuale

```text
Shinra/
├── config/          Caricamento configurazione e template di prompt
├── core/            Logica dell'assistente
│   ├── agent.py         Orchestratore: fast-path, tool calling, risposta
│   ├── ollama_client.py Client del modello locale
│   ├── ha_client.py     Client Home Assistant (REST)
│   ├── data_store.py    Persistenza su file JSON
│   ├── user_manager.py  Profili utente
│   ├── memory.py        Cronologia conversazione
│   ├── timer_engine.py  Timer e promemoria
│   ├── interview_engine.py  Modalita' apprendimento
│   ├── tts_engine.py    Sintesi vocale neurale
│   └── tools/           Funzioni invocabili dal modello
├── server/          FastAPI: app.py (pubblico) + routes_admin.py (gestione)
├── integrations/    Adattatori per canali esterni (oggi: Alexa)
├── web/             Interfaccia: un unico index.html da 4.657 righe
├── data/            Stato runtime in JSON
└── tests/           Suite di test
```

### Flusso di una richiesta

```text
Browser / PWA          Amazon Echo
     │                      │
     │ POST /api/chat       │ POST /api/alexa
     ▼                      ▼
  server/app.py    integrations/alexa/skill_handler.py
     └──────────┬───────────┘
                ▼
        core/agent.py — process_user_input()
                │
     ┌──────────┼───────────────────────────┐
     ▼          ▼                           ▼
 fast-path   contesto                  ciclo tool
 (< 0.2s)   (HA, knowledge,          ┌────┴────┐
             alias, modalita')       ▼         ▼
                                 Ollama    core/tools/*
                                              │
                                              ▼
                                    core/ha_client.py → Home Assistant
```

---

## 3. Struttura target (dalla v0.2.0)

Il codice si sposta sotto `src/` per separare il pacchetto installabile dal
resto del repository, ed evitare che una `import core` risolva per caso sulla
directory di lavoro.

```text
Shinra/
├── src/shinra/
│   ├── __init__.py          __version__
│   ├── config/              impostazioni (pydantic-settings + env)
│   ├── domain/              modelli e regole, senza dipendenze da IO
│   ├── infra/
│   │   ├── db/              SQLAlchemy: modelli, sessione, migrazioni
│   │   ├── homeassistant/   client REST + client WebSocket
│   │   ├── llm/             client Ollama
│   │   └── scheduler/       APScheduler e job persistenti
│   ├── services/            timer, promemoria, intervista, audit, regole
│   ├── skills/              un modulo per capacita' (vedi §4)
│   ├── channels/            web, alexa, satelliti vocali
│   └── api/                 router FastAPI, dipendenze, sicurezza
├── web/                     frontend a moduli ES
├── tests/{unit,integration}
└── migrations/
```

### Regole di dipendenza

Le frecce vanno in una sola direzione. Una violazione e' un errore di
architettura, non uno stile.

```text
api ──▶ services ──▶ domain
 │          │
 │          └──▶ infra
 └──▶ channels ──▶ services
```

- `domain/` non importa nulla dal progetto: niente FastAPI, niente httpx, niente IO.
- `infra/` conosce il mondo esterno ma non conosce `services/`.
- `api/` e `channels/` non parlano mai direttamente a `infra/`.

---

## 4. Come si aggiunge una capacita' nuova

Il motivo per cui questa struttura esiste. Aggiungere «controlla il robot
aspirapolvere» oggi richiede di toccare cinque file sparsi; dalla v0.2.0 sono
quattro passi meccanici, sempre gli stessi.

1. **Il modulo.** Un file in `src/shinra/skills/`, per esempio `vacuum.py`, che
   espone funzioni asincrone tipizzate e uno schema di tool. Non conosce ne'
   FastAPI ne' Alexa.
2. **La registrazione.** Il modulo si dichiara nel registro dei tool. Nessun
   altro file va modificato per renderlo raggiungibile dal modello.
3. **I test.** Almeno un test per il caso felice e uno per l'errore, con le
   chiamate HTTP simulate. Nessuna rete nei test unitari.
4. **La documentazione.** Una voce nel changelog e, se il modulo introduce una
   scelta non ovvia, un ADR in `docs/adr/`.

Un modulo che rispetta questi quattro passi funziona automaticamente da chat,
da PWA e da Alexa, perche' i canali non sanno nulla delle singole capacita'.

---

## 5. Debito noto da estinguere

| Debito | Effetto | Estinto in |
| :--- | :--- | :--- |
| Persistenza su JSON senza lock | Perdita di scritture concorrenti | v0.2.0 |
| Nessuno scheduler | Timer e promemoria non funzionano senza browser | v0.2.0 |
| Memoria globale condivisa | Il contesto di un utente entra in quello di un altro | v0.2.0 |
| Fast-path dentro `process_user_input` (~200 righe) | Non testabile, difficile da estendere | v0.2.0 |
| `index.html` monolitico (4.657 righe) | Ogni modifica al frontend e' rischiosa | v0.5.0 |
| Polling REST verso Home Assistant | Nessun evento, nessuna reattivita' | v0.3.0 |
| Stringhe italiane intrecciate alla logica | Impossibile tradurre | v0.5.0 |
