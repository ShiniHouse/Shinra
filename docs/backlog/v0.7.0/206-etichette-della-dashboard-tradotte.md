---
title: "feat(i18n): le etichette della dashboard escono dal codice"
issue: 206
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: frontend"]
---

## Contesto

Residuo della #36, ed e' la parte che da sola vale il criterio «nessuna stringa
visibile all'utente resta scritta nel codice». Le etichette, i titoli, i
messaggi e i segnaposto della dashboard sono italiani dentro ventitre moduli e
nove pezzi di markup: migliaia di stringhe.

La lingua e' gia' del profilo (#203): una persona che sceglie l'inglese oggi
riceve risposte in inglese dentro un'interfaccia italiana.

## Cosa fare

- [ ] Un meccanismo: un file di traduzioni per lingua in `web/static/lingue/`, servito come gli altri statici, e una funzione `t('chiave', {valori})` in un modulo suo, che non dipende dalle aree
- [ ] Il markup statico usa `data-t="chiave"` per il testo e `data-t-segnaposto` per i segnaposto; il JavaScript usa `t()`
- [ ] La lingua della dashboard e' quella del profilo che ha fatto l'accesso; se la traduzione di una chiave manca si ricade sull'italiano, e la console lo dice una volta
- [ ] Si procede per area, una Pull Request ciascuna, a partire dalle piu' viste: console, navigazione, accesso, impostazioni. Le aree tradotte si elencano in un punto solo
- [ ] Una guardia conta le stringhe italiane rimaste nel codice di ogni area e non le lascia aumentare (come per le violazioni di architettura)

## Criteri di accettazione

- [ ] Cambiare lingua al profilo cambia anche l'interfaccia, senza ricaricare codice
- [ ] Aggiungere una lingua all'interfaccia e' un file, non una modifica ai moduli
- [ ] La guardia esiste e il suo conteggio scende a ogni area tradotta
- [ ] Il valore di una chiave passa da `_html` come ogni altro testo: una traduzione con dentro `<img onerror=...>` non esegue niente
