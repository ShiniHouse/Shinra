---
title: "feat(sicurezza): dispositivi fidati, per non chiedere il PIN ogni volta"
milestone: "v0.2.0"
labels: ["tipo: funzione", "area: sicurezza", "area: frontend"]
riferimento: "ADR 0004"
---

## Contesto

Un PIN per persona rende i permessi reali, ma su un telefono diventa un
fastidio quotidiano. E una protezione fastidiosa viene disattivata: a quel
punto la casa e' aperta come prima, con in piu' l'illusione di essere protetta.

La soluzione e' quella che usano banche e servizi di posta: ricordare il
dispositivo dopo il primo accesso, e permettere di revocarlo.

## Cosa fare

- [ ] Dopo il primo accesso con PIN, offrire «ricorda questo dispositivo» con
      un nome scelto dall'utente («iPhone di Alessio»)
- [ ] Credenziale di dispositivo legata all'utente, in un cookie `HttpOnly`,
      `Secure`, `SameSite=Lax`, valida 30 giorni e rinnovata a ogni uso
- [ ] Elenco dei dispositivi fidati nelle impostazioni: nome, ultimo accesso,
      indirizzo di rete approssimativo, revoca singola
- [ ] «Revoca tutti i dispositivi» in un clic, per il telefono perso
- [ ] Revocare un utente revoca i suoi dispositivi
- [ ] Cambiare il PIN revoca i dispositivi, tranne quello da cui lo si cambia
- [ ] La credenziale identifica il dispositivo, non aumenta i permessi: un
      dispositivo fidato di un profilo bambino resta un profilo bambino

## Criteri di accettazione

- [ ] Dopo aver scelto «ricorda», il PIN non viene piu' chiesto su quel dispositivo
- [ ] Revocare un dispositivo lo riporta a chiedere il PIN al primo accesso
- [ ] «Revoca tutti» disconnette ogni dispositivo tranne quello in uso
- [ ] La credenziale non e' leggibile da JavaScript
- [ ] Un dispositivo fidato non eredita permessi che il suo utente non ha
