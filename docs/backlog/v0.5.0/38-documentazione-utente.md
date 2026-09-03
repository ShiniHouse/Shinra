---
title: "docs: documentazione utente e installazione verificata"
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: documentazione"]
---

## Contesto

Il README e' completo ma descrive uno stato non del tutto reale: promette
privacy totale mentre il riconoscimento vocale passa da Google, e istruisce a
disattivare protezioni del reverse proxy per far funzionare Alexa. Serve una
revisione a fine progetto, quando le funzioni corrispondono alle promesse.

## Cosa fare

- [ ] Riscrivere il README perche' descriva il comportamento reale
- [ ] Guida all'installazione per ciascuna modalita': Docker, add-on, manuale
- [ ] Guida alla configurazione iniziale, dal primo avvio alla prima routine
- [ ] Guida alla risoluzione dei problemi, ricavata dai difetti realmente incontrati
- [ ] Documentazione di riferimento delle API
- [ ] Guida allo sviluppo di un modulo nuovo, secondo `ARCHITECTURE.md` §4
- [ ] **Verifica**: installazione da zero su una macchina pulita seguendo solo la documentazione, annotando ogni punto in cui serve conoscenza non scritta

## Criteri di accettazione

- [ ] Una persona che non conosce il progetto installa e configura Shinra seguendo solo la documentazione
- [ ] Ogni affermazione del README e' verificabile
- [ ] La guida allo sviluppo permette di aggiungere un modulo senza leggere il codice dell'agente
