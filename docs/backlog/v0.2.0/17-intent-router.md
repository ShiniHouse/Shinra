---
title: "refactor(agent): estrarre l'intent router da process_user_input"
milestone: "v0.2.0"
labels: ["tipo: attivita'", "area: core"]
---

## Contesto

`ShinraAgent.process_user_input` e' lungo circa 250 righe e contiene, in
sequenza inline: gestione dell'intervista, parsing di timer e promemoria,
attivazione di modalita', controllo diretto dei dispositivi per alias, meteo,
notizie, Wikipedia, costruzione del prompt e ciclo di tool calling.

Non e' testabile a pezzi, e ogni intento nuovo allunga la stessa funzione.

Ci sono anche due difetti di riconoscimento gia' individuati:

- **Falso positivo sul meteo.** Il fast-path scatta sulla parola `temperatura`,
  quindi «che temperatura c'e' in salotto» interroga Open-Meteo per le previsioni
  esterne invece del sensore interno di Home Assistant.
- **Estrazione della citta' fragile.** L'espressione
  `\b(?:a|ad|per|di)\s+([a-zA-Zaeeiou]+)` cattura una sola parola: «Reggio
  Emilia» e «San Giovanni» si spezzano. Le esclusioni sono una lista scritta a mano.

## Cosa fare

- [ ] Estrarre ogni intento in un handler con interfaccia comune: verifica di applicabilita', priorita', esecuzione
- [ ] Registro degli handler ordinato per priorita', al posto della catena di `if`/`elif`
- [ ] Un intento nuovo si aggiunge registrando un handler, senza toccare l'agente
- [ ] Distinguere temperatura interna (sensore HA) da temperatura esterna (meteo)
- [ ] Estrazione della citta' su nomi composti, verificata contro la geocodifica invece che con una lista di esclusioni
- [ ] Un test per ogni handler

## Criteri di accettazione

- [ ] «Che temperatura c'e' in salotto» legge il sensore, non il meteo
- [ ] «Che tempo fa a Reggio Emilia» risolve la citta' corretta
- [ ] Aggiungere un intento non richiede modifiche a `process_user_input`
- [ ] Ogni handler ha almeno un test, senza rete
