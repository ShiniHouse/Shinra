---
title: "feat(agente): un router e gli agenti di dominio, ciascuno con i propri strumenti"
issue: 190
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Attua la decisione dell'ADR 0008. Oggi un solo ciclo vede tutti gli strumenti.
Con un router e agenti di dominio, ciascun agente vede solo quelli del proprio
ambito: meno scelte davanti, meno errori con un modello piccolo.

## Cosa fare

- [x] Un registro degli agenti: nome, dominio, strumenti consentiti (le istruzioni sono quelle comuni del prompt: un agente non ne ha di proprie)
- [x] Un router che sceglie l'agente con regole e parole chiave per lingua. Il modello non serve (47 frasi su 48 del corpus hanno il dominio giusto) e la scelta e' nel log e nel campo `agenti` della risposta, non nel registro delle azioni
- [x] Primi agenti: otto, uno per modulo del catalogo (casa, clima e tapparelle, dispositivi, sicurezza, energia, informazioni, promemoria, agenda)
- [x] Un agente non puo' invocare uno strumento che non ha dichiarato, anche se il modello lo chiede
- [x] Se il router non sceglie, **il ripiego non e' il percorso di prima**: il modello non riceve strumenti e risponde a parole (il catalogo intero non ci sta nel contesto e invita a indovinare; #289)
- [x] Il `fast-path` sotto i 0,2 secondi resta com'e': un comando semplice non passa dal router

## Criteri di accettazione

- [x] Sul banco di prova gli agenti di dominio fanno meglio del ciclo unico, o la scheda dice il contrario con i numeri
- [x] Un test prova che un agente non puo' chiamare uno strumento fuori dal suo dominio
- [x] `test_architettura.py` resta verde senza nuove eccezioni

## Com'e' andata

Fatti in quattro passi: il router e gli agenti (#284), la modalita' `--agenti` del banco (#285), il prompt di
sistema stabile perche' la cache di Ollama lavori (#286), il ripiego senza strumenti (#289) e il controllo del
bersaglio valido (#290). I numeri sono in `banco/risultati/` (`2026-10-05-i5-8500t-agenti-ANALISI.md`,
`2026-10-05-i7-1355u-ANALISI.md`).

Sul banco, con `qwen2.5:3b` e contesto 4096:

| | Catalogo intero @ 8192 | Agenti, dopo la #289 (portatile) |
| :--- | ---: | ---: |
| Strumento giusto | 72,8% | **79,8%** |
| Riuscite a pieno | 68/114 | **80/114** |
| Inventate | 11 | **3** |
| Mediana | 131 s | **28,7 s** |

Gli agenti fanno meglio del ciclo unico, ma **non raggiungono le soglie dell'ADR 0008** (85% strumento giusto,
75% argomenti, al massimo 1 inventata, mediana sotto 15 s): l'ADR resta Proposto. Il guadagno e' soprattutto di
tempo; con questo modello e queste CPU la precisione resta sotto la soglia, e per tempi da voce serve altro hardware.

Cio' che resta fuori da questa scheda:

- **«spegni tutto»** e **«accendi la luce»** vengono riconosciute dal router ed eseguite, anche se sono ambigue.
  Decisione del 2026-10-06: **restano cosi'**. Una conferma per i comandi che toccano piu' dispositivi si potra'
  aggiungere se la casa ne mostrera' il bisogno.
- Le frasi su due domini ricevono i due agenti uniti, non sono scomposte in due passaggi: se serve, e' la #191.
- Il clima (2/8 sul banco) e gli argomenti troppo rigidi del corpus sono lavoro a parte.
