---
title: "feat(llm): Ollama su un'altra macchina della rete, scelto da configurazione e protetto"
issue: 240
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: infra", "area: sicurezza"]
---

> **Dipende da:** le misure della #183.

## Contesto

Il modello gira dove gira Shinra, su una CPU senza scheda grafica. Separare il **cervello** dalla **casa**
permette di sostituire solo la macchina che fa inferenza (un Mac mini, un mini PC) senza spostare Home
Assistant e Shinra. `base_url` di Ollama e' gia' configurabile, ma nessuno ha deciso cosa succede quando il
server e' lontano: tempi, errori, protezione.

Ollama **non ha autenticazione**: un server dedicato esposto per sbaglio e' un modello aperto a chiunque
raggiunga la porta, e un telecomando verso una casa se Shinra si fida delle sue risposte.

## Cosa fare

- [ ] Configurare per **scopo** l'indirizzo e il modello: chat, embedding, e (in seguito) il sogno e i riassunti
- [ ] Tempi e ripetizioni pensati per una rete: un server lontano che non risponde non blocca la risposta
- [ ] Un controllo di stato che il Cervello mostra: raggiungibile, modello presente, latenza
- [ ] Se il server non risponde: gli intenti deterministici funzionano comunque, il resto dice chiaramente cosa manca (nessun silenzio)
- [ ] Una guida per proteggere l'endpoint: ascolto solo sulla rete locale, firewall aperto al solo indirizzo di Shinra, **mai** dietro Cloudflare ne' con una porta aperta verso Internet; `OLLAMA_HOST` su macOS con un `LaunchAgent`
- [ ] Documentare in `INSTALLAZIONE.md` e `DEPLOY.md`
- [ ] Una prova con un finto server remoto lento o spento

## Criteri di accettazione

- [ ] Shinra risponde usando un Ollama su un'altra macchina, scelto da configurazione
- [ ] Con il server spento una richiesta risolta da un intento funziona, e le altre dicono che il modello non c'e'
- [ ] La guida dice come verificare che l'endpoint **non** sia raggiungibile da fuori la rete di casa
- [ ] Nessun indirizzo o credenziale nei log
