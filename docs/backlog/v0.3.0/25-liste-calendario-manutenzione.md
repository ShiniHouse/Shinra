---
title: "feat(casa): liste condivise, calendario e scadenze di manutenzione"
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Tre entita' semplici che poggiano tutte sul database della v0.2.0 e che oggi
mancano del tutto:

- **Liste condivise.** Nessuna lista della spesa o delle cose da fare, benche' il sistema conosca gia' i profili della famiglia.
- **Calendario.** Nessuna agenda: «cosa ho oggi» non ha risposta.
- **Manutenzione.** Nessuna scadenza: filtri della caldaia, revisione, bollo, garanzie.

## Cosa fare

- [ ] Liste condivise con voci, autore, stato; aggiunta e lettura a voce
- [ ] Integrazione con le entita' `todo` di Home Assistant dove presenti
- [ ] Calendario: lettura dalle entita' `calendar` di Home Assistant, con eventi propri come alternativa
- [ ] Scadenze ricorrenti con promemoria automatico tramite lo scheduler della issue #11
- [ ] Gestione dei documenti collegati a una scadenza (garanzia, fattura)

## Criteri di accettazione

- [ ] «Aggiungi il latte alla lista della spesa» funziona da chat e da Alexa
- [ ] «Cosa ho oggi» elenca gli impegni reali
- [ ] Una scadenza di manutenzione genera un promemoria che scatta davvero
