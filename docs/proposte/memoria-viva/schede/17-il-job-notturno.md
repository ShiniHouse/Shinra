---
title: "feat(scheduler): un compito notturno, con un tetto di tempo e senza far danni"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: infra"]
---

> **Fase D — Il sogno.** Dipende da: Materiali della giornata, budget del contesto.

## Contesto

Il motore dello scheduler ha `programma_periodico` (ogni N ore) e azioni a data: manca, o va verificato, un
compito **a ora fissa**. Il sogno gira di notte su un mini-PC senza GPU: la lentezza non conta, il consumo di
memoria e il tempo massimo si'. Deve poter essere ripetuto senza duplicare niente.

## Cosa fare

- [ ] Un trigger a ora fissa (cron) nel motore, se non c'e'
- [ ] Finestra di tempo massima con interruzione pulita; modello e `num_ctx` dedicati
- [ ] Salta se Ollama e' giu' o la macchina e' carica; si riprova la notte dopo
- [ ] Idempotente per giornata (chiave per data); disattivabile dalle impostazioni; durata e esiti nel log
- [ ] Stato visibile come «sistema» nel grafo del Cervello

## Criteri di accettazione

- [ ] Eseguito due volte nella stessa notte non duplica niente (test)
- [ ] Misura sul i5-8500T: durata e picco di memoria, scritte nella scheda
- [ ] Con Ollama spento termina in un attimo e lo dice
