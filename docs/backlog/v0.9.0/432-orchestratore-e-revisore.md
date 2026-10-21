---
title: "feat(agenti): un orchestratore che scompone e un revisore che controlla l'esito, con i messaggi fra agenti tracciati"
issue: 432
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase C — Piu' agenti.** Dipende da: il banco dei piani (01) e i piani a piu' passaggi (#191). ADR 0008 e 0013.

## Contesto

Gli agenti di dominio ci sono (`services/agenti.py`) ma nessuno ne chiama un altro. Un orchestratore scompone la richiesta e passa i pezzi; un
revisore controlla l'esito prima di dirlo («le luci sono accese davvero?»). **Si usa solo dove il banco (01) dice che aiuta.**

## Cosa fare

- [ ] Un orchestratore che produce l'elenco dei pezzi e a quale agente va ciascuno; ogni agente conserva **solo i suoi strumenti** (il confine sta nel codice che esegue, non nel prompt)
- [ ] Un revisore che verifica lo stato dopo l'esecuzione (rilegge il dispositivo) e dice cosa e' riuscito e cosa no
- [ ] I messaggi fra agenti sono tracciati (eventi `agente.*`) e il Cervello li mostra come percorso
- [ ] Un tetto di passi, di tempo e di costo per richiesta

## Criteri di accettazione

- [ ] Un agente non puo' eseguire uno strumento non suo, comunque un altro agente (o il modello) lo chieda
- [ ] Il banco (01) mostra un miglioramento misurato; se non c'e', la funzione resta spenta
- [ ] Le azioni sensibili passano sempre dalla conferma
