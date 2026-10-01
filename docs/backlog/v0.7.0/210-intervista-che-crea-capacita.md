---
title: "feat(apprendimento): l'intervista parte dalle entita' vere e produce routine complete"
issue: 210
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Residuo della #170, tappa due. Finche' l'intervista raccoglie fatti in prosa, la
casa non impara a *fare* niente di nuovo. Il salto e' che ogni risposta diventi
una capacita': un alias per un dispositivo vero, una routine che si puo'
provare subito.

## Cosa fare

- [ ] Parte dalle entita' di Home Assistant, stanza per stanza: per ciascuna chiede come si chiama in casa, e la risposta diventa un alias
- [ ] Trasforma un'abitudine detta a parole in una routine completa (innesco, condizioni, azioni) usando il grafo dell'editor, mostrata prima di salvare
- [ ] La routine proposta si prova con il simulatore (la casa non cambia) prima di confermarla
- [ ] Un alias o una routine rifiutati non entrano nel database

## Criteri di accettazione

- [ ] Dopo l'intervista ogni entita' nominata ha un alias e la mappa dei dispositivi lo mostra
- [ ] Un'abitudine come «la sera chiudo le tapparelle e accendo la luce del corridoio» diventa una routine che il simulatore esegue fino in fondo
- [ ] Nessuna entita' inventata dal modello entra negli alias (il modello non e' fidato: si valida contro le entita' reali)
