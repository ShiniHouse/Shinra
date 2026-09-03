---
title: "security(api): richiede autenticazione su tutti gli endpoint di gestione"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: sicurezza", "gravita': critica"]
riferimento: SEC-01
---

## Contesto

`is_authenticated()` viene invocata in **un solo endpoint su trentanove**:
`POST /api/settings`.

Restano completamente aperti, fra gli altri:

| Endpoint | Cosa consente |
| :--- | :--- |
| `POST /api/modes/{nome}/activate` | Eseguire una routine domotica |
| `POST /api/chat` | Comandare la casa in linguaggio naturale |
| `GET`/`DELETE /api/users` | Leggere e cancellare l'anagrafica della famiglia |
| `GET /api/knowledge` | Leggere abitudini, orari, dati della casa |
| `GET /api/ha/entities` | Enumerare ogni dispositivo dell'abitazione |
| `POST`/`DELETE /api/aliases`, `/api/modes`, `/api/timers` | Alterare la configurazione |

Con il server in ascolto su `0.0.0.0`, qualunque dispositivo sulla rete di casa
— un ospite sul Wi-Fi, un elettrodomestico compromesso — comanda l'impianto e
scarica i dati della famiglia con una singola `curl`.

## Cosa fare

- [ ] Definire una dipendenza FastAPI `richiedi_autenticazione` e applicarla a livello di router, non endpoint per endpoint
- [ ] Elencare esplicitamente i pochi endpoint pubblici: `GET /` (che poi impone il login lato server, vedi SEC-03), `GET /api/auth/status`, `POST /api/auth/login`, `POST /api/alexa` (protetto invece dalla firma Amazon, vedi SEC-02)
- [ ] Introdurre il principio **protetto per difetto**: un endpoint nuovo e' privato se non dichiara il contrario
- [ ] Distinguere i permessi per ruolo: un profilo `child` non deve poter cancellare utenti ne' modificare le impostazioni
- [ ] Aggiungere un test che elenca le rotte registrate e fallisce se una rotta non e' ne' protetta ne' nella lista delle pubbliche

## Criteri di accettazione

- [ ] `curl -X POST http://host:8000/api/modes/Cinema/activate` senza credenziali risponde `401`
- [ ] `curl http://host:8000/api/users` senza credenziali risponde `401`
- [ ] Il test di inventario delle rotte fallisce se si aggiunge un endpoint senza dichiararne la protezione
- [ ] L'interfaccia web continua a funzionare dopo il login
