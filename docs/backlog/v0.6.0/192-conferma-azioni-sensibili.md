---
title: "feat(sicurezza): le azioni sensibili chiedono sempre conferma, anche dentro un piano"
issue: 192
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: sicurezza", "gravita': alta"]
---

## Contesto

Un principio permanente di Shinra e' che il modello non e' fidato. Un agente
che pianifica da solo e puo' comandare una serratura o disinserire l'allarme
e' esattamente il caso in cui quel principio deve diventare codice. Questa
scheda e' obbligatoria: la fase non si chiude senza.

## Cosa fare

- [x] Una classificazione degli strumenti: sicuri, sensibili (serrature, allarme, apertura di garage e porte), vietati agli agenti
- [x] Un'azione sensibile dentro un piano sospende il piano e chiede conferma al profilo che l'ha richiesto, sul canale da cui e' arrivata
- [x] Da un canale senza identita' sicura (Alexa senza riconoscimento della voce) un'azione sensibile non parte, e lo dice
- [x] Una conferma scade dopo pochi minuti e vale per quel solo piano
- [x] Ogni conferma, rifiuto e scadenza finisce nel registro delle azioni

## Criteri di accettazione

- [x] Un test prova che nessun percorso, nemmeno un piano o un agente, raggiunge una serratura senza conferma
- [x] Un test prova che una conferma scaduta non esegue niente
- [x] Un test prova che la conferma di un profilo non vale per un altro

## Com'e' andata

- `domain/sensibilita.py`: tre classi (sicura, sensibile, vietata agli agenti) e un elenco di
  strumenti sicuri; **uno strumento sconosciuto e' sensibile** (chiuso per difetto), e un test
  fallisce finche' chi lo aggiunge non decide. Il bersaglio puo' essere un `entity_id` o un nome
  naturale: «serratura ingresso» vale come `lock.porta_ingresso`.
- `services/conferme.py` + intento `conferma`: l'azione sensibile non parte, si ricorda cosa e'
  stato chiesto (argomenti compresi) e a chi; il «si'» di **quella persona su quel canale** la
  esegue una volta sola. Il «si'» lo legge un intento che viene prima del modello: il modello non
  puo' darlo da solo. Una frase che non e' un si' secco («si', ma prima...») non conferma.
- Tre minuti di validita'; alla scadenza non parte niente e si scrive nel registro anche se nessuno
  ha piu' parlato. Ogni richiesta, conferma, rifiuto, scadenza e annullamento va nel registro
  (strumento e bersaglio, mai gli argomenti: possono contenere il codice dell'allarme).
- Voce non riconosciuta, o nessun canale a cui chiedere (lo scheduler): l'azione viene rifiutata, e lo dice.
- **Rete di sicurezza in fondo**: `call_service` e `chiama_con_risposta` rifiutano una chiamata che
  apre/disarma quando l'ha scelta il modello senza conferma — copre cio' che il varco non vede
  (un passo dentro una modalita' attivata dal modello).
- Tolte le conferme «ripeti la richiesta» che stavano dentro i due strumenti: erano per dispositivo e
  non per persona (la conferma di un profilo valeva per un altro), e su Alexa soltanto.
- **Piani e agenti (#190, #191)** non esistono ancora: ereditano il varco perche' il varco sta alla
  porta di ogni strumento. Un piano che riceve `conferma_richiesta` deve sospendersi; la sospensione e'
  del piano e arrivera' con lui.
- Limiti noti: gli script di Home Assistant e le scene lanciate da `activate_scene_or_routine` sono
  trattati per nome (gli script sono sempre sensibili, le scene no); le modalita' scritte da una
  persona e attivate da una **frase** (non dal modello) non chiedono conferma: sono scelte esplicite.
  Le regole e le routine automatiche (`regole`, scheduler) non passano da qui: sono cose che una
  persona ha configurato apposta.
