---
title: "perf(frontend): il grafo regge un telefono e un mini-PC"
issue: 187
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

Un grafo con centinaia di nodi e' bello su un portatile e puo' andare a
scatti su un telefono o su un tablet appeso al muro, che e' proprio l'hardware
che il progetto indica per la parola di attivazione. Una demo che scatta non
serve a nessuno.

## Cosa fare

- [ ] Misurare i fotogrammi al secondo su tre dispositivi veri: portatile (fatto: 60 fps), **telefono e tablet da provare** (vedi sotto)
- [ ] ~~Raggruppare in cluster oltre una soglia di nodi~~ — sostituito dalla modalita' leggera: le misure dicono che il costo e' l'animazione, non il numero di nodi disegnati. I gruppi si nascondono gia' dalla legenda
- [x] Ridurre il lavoro quando la scheda non e' in primo piano o il grafo e' fermo (un grafo assestato non richiede fotogrammi; a scheda chiusa un evento dell'agente non ne richiede: test che fallisce senza la guardia)
- [x] Un interruttore per la modalita' leggera, scelto in automatico oltre 400 nodi (Forze del grafo → Modalita' leggera; la scelta di chi guarda vince e si ricorda)

## Criteri di accettazione

- [x] La tabella dispositivo -> fotogrammi al secondo sta nella scheda (sotto): **CPU rallentata in un browser**, non telefoni veri
- [x] Il grafo resta sopra i trenta fotogrammi al secondo sul dispositivo piu' lento, o la modalita' leggera scatta da sola (a 600 nodi e oltre scatta da sola)
- [x] Con la scheda in secondo piano il consumo di CPU scende a quasi zero (zero fotogrammi richiesti, nessun aggiornamento programmato)

## Com'e' andata

**Misurato con un browser vero a CPU rallentata**, non con un telefono vero: `MISURA_GRAFO=1 npx playwright test cervello-prestazioni`
(`tests/gesti/cervello-prestazioni.spec.mjs`). Un grafo sintetico con seme fisso (~1,3 collegamenti per nodo, otto gruppi),
Edge su un portatile i7-1355U. Fotogrammi al secondo **mentre il grafo si assesta** (il momento piu' caro), prima della
modalita' leggera:

| Nodi | CPU normale | 4x piu' lenta | 6x piu' lenta |
| ---: | ---: | ---: | ---: |
| 100 | 60 | 58 | — |
| 300 | 60 | 51–54 | 38–41 |
| 600 | 60 | 38–39 | **25** |
| 1000 | 59 | **25** | **12** (18 s per assestarsi) |

Dopo l'assestamento, **zero fotogrammi** a ogni dimensione: un tablet appeso al muro non lavora.

**Cosa e' cambiato:** la **modalita' leggera** — il grafo si dispone in un colpo e poi sta fermo, come con il movimento ridotto —
si accende da sola oltre i 400 nodi e si sceglie a mano; con 600 o 1000 nodi il grafo e' pronto in meno di un quarto di secondo
dopo il caricamento, a qualunque velocita' di CPU. Sotto i 400 nodi resta l'animazione (36 fps o piu' anche a 6x). E a scheda
chiusa un evento dell'agente non fa piu' disegnare una tela che nessuno vede (prima: 73 fotogrammi per evento).

**Cosa resta:** la casa oggi ha circa 90 nodi (la modalita' leggera non si accende), e **nessun telefono o tablet vero e' stato
provato**. Un telefono e' piu' lento di un portatile ma non sappiamo di quanto: la prova vera e' aprire la scheda Il Cervello sul
telefono e sul tablet e dire se si muove fluida. La scheda resta aperta per questo.
