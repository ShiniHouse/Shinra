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

- [x] Dopo il primo accesso con PIN, offrire «ricorda questo dispositivo» con
      un nome scelto dall'utente («iPhone di Alessio»)
- [x] Credenziale di dispositivo legata all'utente, in un cookie `HttpOnly`,
      `Secure`, `SameSite=Lax`, valida 30 giorni e rinnovata a ogni uso
- [x] Elenco dei dispositivi fidati: rotte `/api/dispositivi` (elenco,
      revoca singola, revoca totale) con nome, ultimo accesso e indirizzo.
      **La schermata nelle impostazioni non c'e' ancora**: va nella stessa PR
      di frontend che porta la gestione dei ruoli (issue #19), perche' sono
      la stessa pagina e lo stesso lavoro.
- [x] «Revoca tutti i dispositivi» in un clic, per il telefono perso
- [x] Revocare un utente revoca i suoi dispositivi
- [x] Cambiare il PIN revoca i dispositivi, tranne quello da cui lo si cambia
- [x] La credenziale identifica il dispositivo, non aumenta i permessi: un
      dispositivo fidato di un profilo bambino resta un profilo bambino

## Criteri di accettazione

- [x] Dopo aver scelto «ricorda», il PIN non viene piu' chiesto su quel dispositivo
- [x] Revocare un dispositivo lo riporta a chiedere il PIN al primo accesso
- [x] «Revoca tutti» disconnette ogni dispositivo tranne quello in uso
- [x] La credenziale non e' leggibile da JavaScript
- [x] Un dispositivo fidato non eredita permessi che il suo utente non ha
