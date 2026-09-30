---
title: "feat(plugin): un manifesto per le skill aggiuntive, con permessi dichiarati"
issue: 193
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core", "area: sicurezza"]
---

## Contesto

Oggi aggiungere una capacita' vuol dire modificare il codice. Un plugin e' una
cartella con un manifesto che dice cosa fa e di cosa ha bisogno. Caricare
codice altrui dentro un processo che comanda la casa e' la superficie di
attacco peggiore possibile, quindi la scheda va in due tempi: prima il
manifesto e i permessi, e solo se reggono si pensa all'isolamento.

## Cosa fare

- [ ] Formato del manifesto: nome, versione, strumenti esposti, permessi richiesti (domini di Home Assistant, rete verso quali host, lettura della conoscenza)
- [ ] Un plugin non dichiarato non si carica; un permesso non dichiarato non si concede
- [ ] Un plugin di terzi e' spento finche' l'utente non lo abilita, leggendo i permessi che chiede
- [ ] Il registro delle azioni dice quale plugin ha fatto cosa
- [ ] Un plugin che va in errore non abbatte il servizio
- [ ] Decisione scritta su dove gira: nel processo oppure in un processo separato, con il perche'

## Criteri di accettazione

- [ ] Un plugin di esempio, nel repository, viene caricato e invocato da un agente
- [ ] Un test prova che un plugin non puo' comandare un dominio che non ha dichiarato
- [ ] Un plugin che solleva un'eccezione produce un errore leggibile e il resto funziona
