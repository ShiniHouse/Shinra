---
title: "feat(agente): un router e gli agenti di dominio, ciascuno con i propri strumenti"
issue: 190
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Attua la decisione dell'ADR 0008. Oggi un solo ciclo vede tutti gli strumenti.
Con un router e agenti di dominio, ciascun agente vede solo quelli del proprio
ambito: meno scelte davanti, meno errori con un modello piccolo.

## Cosa fare

- [ ] Un registro degli agenti: nome, dominio, strumenti consentiti, istruzioni
- [ ] Un router che sceglie l'agente (prima con regole e parole chiave, poi col modello se serve), con la scelta registrata nel registro delle azioni
- [ ] Primi agenti: luci e prese, clima e tapparelle, sicurezza (allarme, aperture), energia, agenda (timer, promemoria, liste)
- [ ] Un agente non puo' invocare uno strumento che non ha dichiarato, anche se il modello lo chiede
- [ ] Il percorso attuale senza agenti resta disponibile come ripiego se il router non sceglie
- [ ] Il `fast-path` sotto i 0,2 secondi resta com'e': un comando semplice non passa dal router

## Criteri di accettazione

- [ ] Sul banco di prova gli agenti di dominio fanno meglio del ciclo unico, o la scheda dice il contrario con i numeri
- [ ] Un test prova che un agente non puo' chiamare uno strumento fuori dal suo dominio
- [ ] `test_architettura.py` resta verde senza nuove eccezioni
