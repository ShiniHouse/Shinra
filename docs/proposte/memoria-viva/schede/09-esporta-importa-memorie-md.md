---
title: "feat(conoscenza): esporta e importa i ricordi come un file Markdown leggibile"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase B — Trasparenza.** Dipende da: ADR privacy, API della memoria.

## Contesto

Un file `MEMORIE.md` leggibile e modificabile con un editor e' un'idea buona per la trasparenza. Tenerlo
**sincronizzato di continuo** con il database non lo e': due fonti di verita' producono conflitti, un
salvataggio a meta' lascia un file incoerente, e un file su disco **aggira i permessi** (chiunque legga il
disco legge la memoria privata di tutti). La proposta: il database resta la fonte, il file e' una vista.

## Cosa fare

- [ ] Esportare (per profilo o per la casa) in Markdown leggibile, con gli identificativi in commenti invisibili
- [ ] Importare con **anteprima delle differenze** (nuovi, modificati, tolti) e conferma: niente scritture silenziose
- [ ] Nessuna sincronizzazione continua; l'esportazione dichiara che il file contiene dati personali
- [ ] Nessun segreto nel file (stessa regola del backup)

## Criteri di accettazione

- [ ] Esporta e reimporta senza differenze (round trip)
- [ ] Un file ostile (identificativi di altri profili, testi con istruzioni) non scrive fuori ambito e non crea stato attivo senza conferma
