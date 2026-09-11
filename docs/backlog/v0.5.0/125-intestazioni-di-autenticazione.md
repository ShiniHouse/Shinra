---
title: "fix(interfaccia): le chiamate all'API partono senza le intestazioni di autenticazione"
issue: 125
milestone: "v0.5.0"
labels: ["tipo: difetto", "area: frontend", "gravita': alta"]
---

## Contesto

Ventisette chiamate su settantatre, in `web/templates/index.html`, partono
senza `getAuthHeaders()`. Fra queste: `/api/regole`, `/api/modes`,
`/api/timers`, `/api/reminders`, `/api/aliases`, `/api/sources`,
`/api/settings`, `/api/status`.

Funzionano sul computer di casa perche' quel browser e' un dispositivo fidato
e il riconoscimento passa dal cookie (`sessione_dalla_richiesta` ha quella
seconda strada). Su un browser non ancora fidato — il telefono di un ospite,
una finestra anonima, la PWA appena installata — quelle rotte rispondono 401.

E il 401 non si vede. Il codice fa:

```js
const dati = await res.json();
renderRegole(dati.regole || []);
```

Un corpo `{"detail": "..."}` diventa `[]`, e la schermata mostra «non c'e'
niente» invece di «non ho il permesso di vederlo». Sono due cose diverse che
oggi hanno lo stesso aspetto in una decina di schermate — ed e' la stessa
famiglia del difetto del microfono chiuso con la #113: la rotta era giusta,
mancava un'intestazione.

## Cosa fare

- [ ] Aggiungere `getAuthHeaders()` a tutte le chiamate che ne sono prive, tranne `/api/auth/profili` e `/api/auth/login`, che per definizione precedono la sessione
- [ ] Rendere visibile un rifiuto: una chiamata che torna 401 o 403 deve dirlo nella schermata, non lasciare una lista vuota
- [ ] Guardia: ogni `fetch` verso `/api/` porta le intestazioni, salvo le due eccezioni dichiarate per nome

## Criteri di accettazione

- [ ] Un browser mai autenticato e non fidato vede tutte le schermate popolate dopo il PIN
- [ ] Una schermata che non puo' leggere i suoi dati lo dice, e dice perche'
- [ ] La guardia fallisce se una fetch nuova nasce senza intestazioni
