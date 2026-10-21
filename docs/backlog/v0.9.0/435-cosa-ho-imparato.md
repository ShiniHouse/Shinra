---
title: "feat(frontend): la scheda «Cosa ho imparato», con l'annulla a un clic"
issue: 435
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: frontend"]
---

> **Fase D.** Dipende da: il ciclo dell'imparare (04). Estende la scheda *Stanotte ho notato*, non aggiunge un ingresso.

## Contesto

Una casa che cambia comportamento deve poter dire **cosa e' cambiato, perche', e con quale prova**, e permettere di tornare indietro subito. Senza,
la fiducia dura finche' non sbaglia la prima volta.

## Cosa fare

- [ ] Nella scheda dei suggerimenti: le proposte in attesa (accetta / scarta) e lo storico di cio' che e' stato accettato, con il motivo e la prova
- [ ] Un «annulla» a un clic su ogni accettazione, e un «annulla tutto di oggi»
- [ ] Tutto con `_html`/`_args`, moduli ES, e leggibile dal telefono

## Criteri di accettazione

- [ ] Una prova dei gesti (Playwright): accetta, vedi, annulla
- [ ] Un testo ostile nel motivo resta testo
