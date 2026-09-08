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

Dalla v0.2.0 il codice sta sotto `src/`, diviso per livelli. La struttura e'
quella descritta nel §3: qui c'e' cosa contiene ciascuna cartella.

```text
Shinra/
├── src/shinra/
│   ├── percorsi.py      Dove sta il progetto. Calcolato una volta sola
│   ├── versione.py      Numero e commit in esecuzione
│   ├── avvio.py         Punto di ingresso: il comando `shinra`
│   ├── config/          Impostazioni, segreti, template di prompt
│   ├── domain/          Regole senza IO: argomenti vietati, bus di eventi
│   ├── infra/           Il mondo esterno
│   │   ├── db/              SQLAlchemy: motore, modelli, depositi, import
│   │   ├── homeassistant/   Client REST
│   │   ├── llm/             Client Ollama
│   │   ├── scheduler/       APScheduler con archivio persistente
│   │   ├── data_store.py    I file JSON rimasti
│   │   └── tts.py           Sintesi vocale neurale
│   ├── services/        Agente, memoria, registro, permessi, profili,
│   │   └── intenti/         timer, intervista, consegna — e il router
│   ├── skills/          Le capacita' invocabili dal modello
│   ├── channels/alexa/  Adattatore per l'Echo
│   └── api/             FastAPI: app, rotte, sicurezza, dispositivi
├── web/             Interfaccia: un unico index.html
├── migrazioni/      Alembic
├── data/            Stato runtime (database e file JSON)
└── tests/           Suite di test
```

Le regole di dipendenza fra i livelli sono nel §3 e non sono un'aspirazione:
`tests/unit/test_architettura.py` le verifica a ogni esecuzione della suite.
Le violazioni che restano dallo spostamento sono elencate una per una in
quel file, con il motivo di ciascuna: una nuova fa fallire i test, e una
riparata pure — cosi' l'elenco si accorcia invece di ingrassare.

### Flusso di una richiesta

```text
Browser / PWA          Amazon Echo
     │                      │
     │ POST /api/chat       │ POST /api/alexa
     ▼                      ▼
  api/app.py       channels/alexa/skill_handler.py
     └──────────┬───────────┘
                ▼
        services/agent.py — process_user_input()
                │
     ┌──────────┼───────────────────────────┐
     ▼          ▼                           ▼
 fast-path   contesto                  ciclo tool
 (< 0.2s)   (HA, knowledge,          ┌────┴────┐
             alias, modalita')       ▼         ▼
                                 Ollama     skills/*
                                              │
                                              ▼
                                    infra/homeassistant → Home Assistant
```

---

## 3. Regole di dipendenza

Il codice sta sotto `src/` per separare il pacchetto installabile dal resto
del repository, ed evitare che una `import config` risolva per caso sulla
directory di lavoro invece che sul progetto. Ma il motivo vero e' un altro:
i livelli sono cartelle, quindi la regola che segue si puo' verificare
invece che raccomandare.

Le frecce vanno in una sola direzione. Una violazione e' un errore di
architettura, non uno stile.

```text
api ──▶ services ──▶ domain
 │          │
 │          ├──▶ skills ──▶ infra
 │          └──▶ infra
 └──▶ channels ──▶ services
```

- `domain/` non importa nulla dal progetto: niente FastAPI, niente httpx, niente IO.
- `infra/` conosce il mondo esterno ma non conosce `services/`.
- `skills/` sta sopra l'infrastruttura e sotto chi la orchestra: una capacita'
  non conosce ne' le rotte ne' i canali.
- `api/` e `channels/` non parlano mai direttamente a `infra/`.

`tests/unit/test_architettura.py` verifica tutto questo a ogni esecuzione
della suite. Le diciannove violazioni ereditate dallo spostamento sono
elencate li' una per una, con il motivo: una nuova fa fallire i test, e una
riparata pure — l'elenco puo' solo accorciarsi.

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
