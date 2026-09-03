---
title: "feat(automazioni): motore di regole con trigger su evento, stato e orario"
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: core", "gravita': alta"]
---

## Contesto

Il sistema e' puramente reattivo: risponde soltanto quando gli si parla. Le
"modalita'" esistenti sono sequenze di azioni, non automazioni: si attivano solo
con una frase.

Con lo scheduler (issue #11) e gli eventi Home Assistant (issue #19) disponibili,
mancano solo i trigger.

## Cosa fare

- [ ] Modello di regola: trigger, condizioni, azioni
- [ ] Trigger su evento (una porta si apre), su stato (temperatura sotto una soglia), su orario (ogni giorno alle 7), su presenza, su alba e tramonto
- [ ] Condizioni componibili: orario, presenza, stato di un'entita', giorno della settimana
- [ ] Riuso del grafo di esecuzione gia' presente in `activate_mode`
- [ ] Protezione contro i cicli: una regola che ne innesca un'altra non deve avvitarsi
- [ ] Registro di ogni attivazione, per la spiegabilita'

## Criteri di accettazione

- [ ] Una regola «se la porta si apre dopo le 23, accendi l'ingresso» funziona senza intervento
- [ ] Una regola a orario scatta anche a browser chiuso
- [ ] Due regole che si innescano a vicenda vengono fermate e segnalate
- [ ] Ogni attivazione e' tracciata nel registro
