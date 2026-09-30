---
title: "perf(frontend): il grafo regge un telefono e un mini-PC"
issue: 187
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

Un grafo con centinaia di nodi e' bello su un portatile e puo' andare a
scatti su un telefono o su un tablet appeso al muro, che e' proprio l'hardware
che il progetto indica per la parola di attivazione. Una demo che scatta non
serve a nessuno.

## Cosa fare

- [ ] Misurare i fotogrammi al secondo su tre dispositivi veri: portatile, telefono, tablet
- [ ] Raggruppare in cluster oltre una soglia di nodi; aprire un cluster mostra i suoi nodi
- [ ] Ridurre il lavoro quando la scheda non e' in primo piano o il grafo e' fermo
- [ ] Un interruttore per la modalita' leggera, scelto in automatico sui dispositivi lenti

## Criteri di accettazione

- [ ] La tabella dispositivo -> fotogrammi al secondo sta nella scheda, non solo nella testa di chi l'ha misurata
- [ ] Il grafo resta sopra i trenta fotogrammi al secondo sul dispositivo piu' lento, o la modalita' leggera scatta da sola
- [ ] Con la scheda in secondo piano il consumo di CPU scende a quasi zero
