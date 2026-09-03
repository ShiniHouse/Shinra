---
title: "security(web): il blocco della dashboard deve avvenire sul server"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: sicurezza", "area: frontend", "gravita': alta"]
riferimento: SEC-03
---

## Contesto

`checkAuthStatus()` in `web/templates/index.html:1515` mostra la schermata di
blocco impostando `lockModal.style.display = 'flex'`. A quel punto la dashboard
completa e' gia' stata inviata al browser e le chiamate API partono comunque.

Chiudere l'overlay dagli strumenti sviluppatore, o semplicemente disabilitare
JavaScript, restituisce il pannello intero. L'impostazione `protect_dashboard`
comunica una protezione che non esiste.

## Cosa fare

- [ ] `GET /` verifica la sessione lato server: senza sessione valida serve una pagina di login minimale, non la dashboard
- [ ] Spostare il token di sessione in un cookie `HttpOnly`, `Secure`, `SameSite=Lax`, invece che in `sessionStorage` dove qualsiasi script lo legge
- [ ] Mantenere l'overlay solo come blocco per inattivita' all'interno di una sessione gia' aperta, non come misura di sicurezza
- [ ] Redirigere al login quando una chiamata API risponde `401`

## Criteri di accettazione

- [ ] `curl http://host:8000/` senza sessione non restituisce il markup della dashboard
- [ ] Disabilitare JavaScript non da' accesso ad alcun dato
- [ ] Il token non e' leggibile da `document.cookie` ne' da `sessionStorage`
- [ ] Dopo il login l'esperienza d'uso e' invariata
