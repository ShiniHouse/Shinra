---
title: "feat(conoscenza): recupero per similarita' al posto dell'iniezione totale"
issue: 32
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`get_enabled_knowledge_summary()` concatena **tutti** i fatti abilitati e li
inietta nel prompt di sistema a ogni richiesta. Con la Modalita' Apprendimento
funzionante (v0.1.0) la conoscenza crescera' rapidamente, e il contesto cresce
linearmente con essa: prima si paga in latenza, poi si satura la finestra e i
fatti piu' vecchi vengono silenziosamente troncati.

Il problema e' aggravato dalla configurazione attuale, che imposta `num_ctx` a
1024 o 2048 token.

## Cosa fare

- [x] Calcolo degli embedding tramite Ollama, quindi **in casa**. Un servizio nel
      cloud sarebbe piu' veloce e migliore, e vorrebbe dire mandare a qualcun
      altro il nome del gatto e dove si nasconde la chiave di scorta
- [x] Recupero dei soli fatti pertinenti, con soglia e numero massimo. **Sotto i
      venticinque fatti si manda tutto**, come si e' sempre fatto: il problema
      esiste a duecento fatti, non a venti, e un recupero imperfetto dove non
      serviva farebbe perdere risposte che prima funzionavano
- [x] Ricalcolo alla modifica, **senza doverlo chiedere**: accanto al vettore si
      salva l'impronta del testo, e se non corrisponde il vettore e' vecchio. Un
      vettore vecchio non da' errore, da' risposte sbagliate
- [x] Ricerca ibrida. I vettori sbagliano proprio dove fa male: avvicinano «la
      password del wifi» a «la chiave della rete» — ed e' cio' che serve — ma
      appiattiscono «4471» e «4417» sullo stesso punto, perche' semanticamente
      sono entrambi «un numero». I numeri pesano doppio nella meta' testuale
- [x] `GET /api/conoscenza/fatti-usati` dice quali fatti hanno contribuito e con
      quale punteggio, semantico e testuale separati. Quando l'assistente dice
      una cosa strana, la prima domanda e' «da dove l'ha presa»

## Criteri di accettazione

- [x] Con cinquecento fatti memorizzati, il contesto resta di dimensione costante
      — e contiene comunque la risposta: un contesto costante che non contiene
      cio' che serve sarebbe una regressione, non un miglioramento
- [x] Una domanda specifica recupera i fatti pertinenti e non gli altri
- [x] La latenza non peggiora: sotto la soglia non si chiama nemmeno Ollama, e
      sopra si fa una chiamata di embedding sola per la domanda

## La regola che governa tutto

**Il recupero non deve mai far sapere alla casa meno di prima.**

Da qui discendono le tre scelte che contano: sotto la soglia si manda tutto;
senza embedding — Ollama spento, modello non installato — resta la strada
testuale; e un fatto senza vettore non e' un fatto che non esiste. In tutti
questi casi la casa risponde peggio invece di rispondere «non lo so».

## Cosa hanno trovato i controlli

**Il guardiano della #26** ha bocciato `modello_embedding`, letto con un
`getattr`: sarebbe stata configurazione fantasma, come le tariffe
dell'energia. Adesso si legge per esteso.

**Ruff** ha trovato un difetto vero, non di stile: `asyncio.create_task` senza
riferimento. Un task che nessuno tiene puo' essere raccolto dal garbage
collector a meta', e l'indice resterebbe fatto per meta' senza che niente lo
dica.

**Il controllo di mutazione** ha trovato due test che non mordevano:

- quello sulla soglia guardava una domanda che non aveva **nessuna** parola in
  comune con i fatti, quindi venivano scartati prima di arrivare alla soglia;
- quello sui numeri guardava solo che «4471» battesse «4417», confronto che
  vince anche il conteggio semplice. Adesso guarda un caso dove il raddoppio
  cambia **chi vince**.
