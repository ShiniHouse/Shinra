---
title: "security(auth): PIN con hash, login corretto e rate limit dietro proxy"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: sicurezza", "gravita': alta"]
riferimento: SEC-04
---

## Contesto

Tre difetti nello stesso punto, `server/routes_admin.py`.

**Login permissivo (riga 78).** La condizione e'
`if not expected_pin or provided_pin == expected_pin`: se il PIN non e'
configurato, il login restituisce comunque un token valido per sette giorni.
Qualunque stringa entra.

**Rate limit inefficace.** `FAILED_ATTEMPTS` e' indicizzato su
`request.client.host`, che dietro il reverse proxy consigliato nel README vale
`127.0.0.1` per tutti. Il quinto tentativo sbagliato di un attaccante blocca
per cinque minuti il proprietario di casa, e viceversa. `X-Forwarded-For` non
viene mai letto.

**Confronto vulnerabile ai tempi.** Il PIN si confronta con `==`, in chiaro.

## Cosa fare

- [ ] Rifiutare il login quando nessun PIN e' configurato, invece di accettarlo
- [ ] Salvare il PIN come hash (`argon2` o `bcrypt`), mai in chiaro
- [ ] Migrare automaticamente un PIN in chiaro esistente al primo avvio
- [ ] Confronto a tempo costante
- [ ] Leggere l'IP reale da `X-Forwarded-For` **solo se la richiesta proviene da un proxy elencato come fidato** in configurazione, altrimenti usare `request.client.host`
- [ ] Firmare i token di sessione con `SHINRA_SESSION_SECRET`, che oggi e' dichiarato e mai usato
- [ ] Ridurre la durata della sessione da sette giorni a un valore configurabile, con un giorno come predefinito

## Criteri di accettazione

- [ ] Senza PIN configurato, `POST /api/auth/login` risponde `401` con qualsiasi valore
- [ ] Il PIN non compare in chiaro ne' in configurazione ne' nei log
- [ ] Cinque tentativi falliti da un client non bloccano un client diverso, dietro reverse proxy
- [ ] Un `X-Forwarded-For` contraffatto da un client non fidato viene ignorato
- [ ] Le sessioni esistenti restano valide dopo l'aggiornamento, o l'utente e' informato che deve rifare il login
