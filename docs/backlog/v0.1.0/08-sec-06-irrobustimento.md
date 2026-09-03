---
title: "security(server): debug disattivato, header di sicurezza e CORS"
milestone: "v0.1.0"
labels: ["tipo: attivita'", "area: sicurezza", "gravita': media"]
riferimento: SEC-06
---

## Contesto

Diverse impostazioni di irrobustimento mancano o sono errate:

- `config.yaml` ha `debug: true`, quindi `run.py` avvia uvicorn con `reload=True`: in produzione ricarica il processo a ogni scrittura su file e mostra tracce di errore complete.
- Nessun header di sicurezza sulle risposte.
- Nessuna politica CORS: il comportamento predefinito e' permissivo per le richieste semplici.
- `restricted_topics` esiste in `UserProfile` e **non e' applicato da nessuna riga**: il profilo `child` cambia solo il tono del prompt, non cio' a cui puo' accedere.
- Le eccezioni non gestite espongono la traccia interna al client.

## Cosa fare

- [ ] `debug: false` come predefinito; il reload si abilita solo con una variabile d'ambiente esplicita di sviluppo
- [ ] Aggiungere gli header: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Content-Security-Policy` compatibile con la PWA
- [ ] CORS chiuso per difetto, con lista di origini configurabile
- [ ] Gestore globale delle eccezioni: messaggio generico al client, traccia completa nel log
- [ ] Applicare `restricted_topics` come filtro reale prima dell'invio al modello e sulla risposta
- [ ] Documentare in `README.md` che il servizio va esposto solo dietro HTTPS
- [ ] Aggiungere `GET /health`: endpoint pubblico che risponde `200` se il processo e' vivo, **senza esporre alcuna informazione** (niente modelli, niente URL di Home Assistant, niente stato dei servizi). Serve allo script di distribuzione, che oggi deve interrogare `/api/status` e accettare qualsiasi codice HTTP perche' quell'endpoint diventera' autenticato. Vedi `docs/DEPLOY.md`.

## Criteri di accettazione

- [ ] Gli header di sicurezza sono presenti su ogni risposta
- [ ] Un errore interno restituisce un messaggio generico, e la traccia e' nel log
- [ ] Un profilo con un argomento vietato non riceve risposta su quell'argomento
- [ ] Il servizio avviato senza variabili di sviluppo non ha il reload attivo
- [ ] `GET /health` risponde `200` senza autenticazione e il suo corpo non contiene configurazione
