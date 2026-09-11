---
title: "feat(voce): parola di attivazione locale"
issue: 30
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Non esiste alcuna parola di attivazione: bisogna premere il pulsante del
microfono oppure passare da Alexa. Un assistente domestico che richiede di
toccare uno schermo perde gran parte della propria ragione d'essere.

## Perche' e' stata spostata in v0.5.0

*Deciso l'11 settembre 2026, con Alessio.*

Due criteri di accettazione di questa scheda si verificano **solo con un
microfono vero acceso per giorni**:

> I falsi positivi restano sotto una soglia accettabile in uso reale

Una soglia di sensibilita' si taglia sui falsi positivi che si contano, non
su un numero scelto perche' sembra ragionevole. Non c'e' modo di misurarli
senza che la casa ascolti davvero, e non c'e' hardware su cui farlo: l'unico
microfono disponibile e' quello del browser.

Si poteva scrivere il codice lo stesso. Non si e' fatto, e la ragione e' che
in questa stessa versione sono venuti fuori **tre difetti della stessa
forma** — l'editor a nodi che non salvava, le regole del sole mai
programmate, le regole a orario che rispondevano 500 — tutti in funzioni
spedite e mai eseguite davvero. Una parola di attivazione mai ascoltata da un
microfono sarebbe il quarto.

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

## Cosa c'e' gia', e che serve a questa scheda

La strada che l'audio percorre e' gia' costruita dalla issue #31: la
dashboard registra, manda al **proprio** server, e Whisper trascrive in
casa. Manca solo chi preme il pulsante al posto di una mano.

La issue #33 ha aggiunto il pezzo che rende utile una parola di attivazione
in piu' stanze: un punto di ascolto sa **dove si trova**, e chi sente per
primo risponde. Senza quello, tre dispositivi svegliati dalla stessa parola
avrebbero risposto tutti e tre.

Resta da decidere **dove** gira il riconoscimento. Con un microfono sul
server, openWakeWord in Python e' la strada diretta. Con il solo browser,
serve portare i modelli ONNX nella pagina — e li' il criterio «l'audio prima
dell'attivazione non lascia mai il dispositivo» si rispetta per costruzione,
perche' il browser non manda niente finche' non ha sentito la parola.
