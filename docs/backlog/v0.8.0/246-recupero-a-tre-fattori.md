---
title: "feat(conoscenza): il recupero pesa anche l'importanza, la recenza e l'uso"
issue: 246
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase A — Le fondamenta.** Dipende da: Schema della memoria, banco di valutazione.

## Contesto

`domain/recupero.py` ordina i fatti per `0.7 x vettore + 0.3 x testo`: e' la meta' ibrida gia' fatta
(e ben ragionata: il testo serve per «4471», i vettori per «la chiave della rete»). Mancano tre cose che
una memoria che invecchia richiede: cosa **conta di piu'**, cosa e' **recente**, cosa si e' **usato**.

Attenzione a due fatti: (1) sotto i **25 fatti** (`SOGLIA_RECUPERO`) si mandano tutti, quindi questo
ranking cambia qualcosa solo oltre quella soglia — va misurato su quanti ne ha la casa vera; (2)
l'importanza non si indovina: parte da 3, la alza chi la corregge o chi conferma una proposta.

## Cosa fare

- [ ] Punteggio = somiglianza (come oggi) + importanza normalizzata + recenza (decadimento esponenziale, emivita configurabile, su `max(ultimo_uso, creato_il)`) + un piccolo rinforzo logaritmico per gli usi
- [ ] Tutto in `domain/recupero.py`, puro e senza rete; pesi in configurazione; `spiega()` dice quanto ha pesato ogni fattore
- [ ] I ricordi di importanza massima («fissati») entrano sempre, dentro il budget
- [ ] Sotto la soglia dei 25 fatti il comportamento non cambia

## Criteri di accettazione

- [ ] Sul banco di valutazione, recall@k e MRR non peggiorano rispetto a oggi, e migliorano — oppure la scheda dice che non migliorano e il peso resta a zero
- [ ] Un'ablazione per fattore mostra cosa porta ciascuno
- [ ] Test deterministici sulla formula, compresi i casi limite (nessun uso, nessuna data)
