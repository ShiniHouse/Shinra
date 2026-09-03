---
title: "feat(voce): parola di attivazione locale"
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Non esiste alcuna parola di attivazione: bisogna premere il pulsante del
microfono oppure passare da Alexa. Un assistente domestico che richiede di
toccare uno schermo perde gran parte della propria ragione d'essere.

## Cosa fare

- [ ] Integrare openWakeWord, che gira su CPU
- [ ] Parola personalizzabile, coerente con il nome scelto per l'assistente
- [ ] Soglia di sensibilita' regolabile
- [ ] Indicatore visivo di ascolto e possibilita' di disattivare il microfono, anche fisicamente
- [ ] Nessuna registrazione persistente dell'audio; l'audio prima dell'attivazione non lascia mai il dispositivo

## Criteri di accettazione

- [ ] Pronunciare la parola di attivazione avvia l'ascolto senza toccare nulla
- [ ] I falsi positivi restano sotto una soglia accettabile in uso reale
- [ ] Lo stato del microfono e' sempre visibile
- [ ] Nessun audio viene salvato su disco
