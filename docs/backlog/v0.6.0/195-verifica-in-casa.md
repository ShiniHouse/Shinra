---
title: "test(casa): una regola e un piano scattano davvero in una casa vera"
issue: 195
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: core"]
---

## Contesto

Il criterio della `0.4.0` «una regola creata dall'interfaccia scatta da sola
su un evento reale» e' ancora **da verificare in casa**: il motore funziona e
i test coprono la catena, ma nessuno ha guardato una regola scattare davvero.
Nella `0.5.0` sono venuti fuori tre difetti della stessa forma, tutti in
funzioni spedite e mai eseguite. La `0.6.0` aggiunge agenti e piani: lo stesso
rischio, moltiplicato.

## Cosa fare

- [ ] Una lista di verifiche da eseguire in casa, con esito: regola su evento, regola a orario, regola sul sole, piano a piu' passaggi, conferma di un'azione sensibile
- [ ] Per ciascuna: cosa si e' fatto, cosa si e' visto, cosa diceva il registro delle azioni
- [ ] Ogni difetto trovato diventa una issue, con un test che lo avrebbe trovato
- [ ] Aggiornare la roadmap: il criterio della `0.4.0` passa da «da verificare» a «verificato» o a «non raggiunto»

## Criteri di accettazione

- [ ] La lista e' compilata da chi vive nella casa, non dedotta dai test
- [ ] Nessuna voce e' segnata verificata senza una riga del registro che la prova
