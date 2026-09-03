---
title: "security(alexa): verifica la firma Amazon e l'applicationId"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: sicurezza", "area: integrazioni", "gravita': critica"]
riferimento: SEC-02
---

## Contesto

`POST /api/alexa` esegue comandi domotici senza alcuna verifica dell'origine:

1. Non controlla gli header `Signature` e `SignatureCertChainUrl` richiesti da Amazon.
2. Non confronta l'`applicationId` della richiesta con `settings.alexa.skill_id`,
   che e' configurabile ma **non viene letto da nessuna riga di codice**.
3. Non verifica il campo `timestamp`, che protegge dai replay.

Il README, inoltre, istruisce a disattivare «Block Common Exploits» sul reverse
proxy e a creare una regola Cloudflare che salta il WAF proprio su quel percorso.

Il risultato: **una POST JSON di dieci righe da qualsiasi punto di Internet
comanda l'impianto di casa.** E' il difetto piu' grave del progetto, perche' e'
l'unico raggiungibile dall'esterno.

## Cosa fare

- [ ] Implementare la verifica della firma secondo la specifica Amazon: scaricare la catena di certificati dall'URL indicato, validarne il dominio (`s3.amazonaws.com/echo.api/`), verificare che il certificato includa `echo-api.amazon.com` nei SAN, controllare la validita' temporale e verificare la firma sul corpo grezzo
- [ ] Mettere in cache i certificati per non scaricarli a ogni richiesta
- [ ] Confrontare `session.application.applicationId` con `SHINRA_ALEXA_SKILL_ID`; se la variabile non e' impostata, **rifiutare** invece di accettare
- [ ] Verificare che il `timestamp` non sia piu' vecchio di 150 secondi
- [ ] Leggere il corpo grezzo prima del parsing JSON: la firma si calcola sui byte esatti
- [ ] Aggiornare `ALEXA_SETUP_GUIDE.md` e `README.md` rimuovendo il consiglio di disattivare le protezioni del proxy

## Criteri di accettazione

- [ ] Una POST senza header di firma risponde `400`
- [ ] Una POST con firma non valida risponde `400`
- [ ] Una POST con `applicationId` diverso da quello configurato risponde `400`
- [ ] Una POST con timestamp piu' vecchio di 150 secondi risponde `400`
- [ ] Una richiesta reale da un dispositivo Echo continua a funzionare
- [ ] Esiste un test con richieste firmate e non firmate, senza rete
