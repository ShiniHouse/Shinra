---
title: "feat(db): un ricordo ha un proprietario, un'origine, un'importanza e una storia"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: infra"]
---

> **Fase A — Le fondamenta.** Dipende da: ADR sulla privacy della memoria.

## Contesto

`knowledge` ha cinque colonne: `id`, `text`, `category`, `enabled`, `creato_il`. Per la memoria a tre
livelli servono: **chi** (proprietario), **da dove** (origine), **quanto conta** (importanza), **quando
e quanto e' stato usato** (recenza e rinforzo) e **in che stato e'** (attivo, proposto, archiviato).
Senza, il ranking e le viste per profilo non hanno su cosa lavorare.

## Cosa fare

- [ ] Migrazione Alembic: `proprietario` (vuoto = casa), `origine` (manuale, intervista, conversazione, sogno, importato), `importanza` (1-5, predefinita 3), `ultimo_uso`, `usi`, `stato` (attivo, proposto, archiviato), `aggiornato_il`
- [ ] Riempimento dei dati esistenti: tutto della casa, origine ricavata dove possibile (l'intervista scrive gia' `add_knowledge_item`)
- [ ] `salvataggio` (backup e ripristino): campi nuovi nell'archivio, con la migrazione di schema che il modulo gia' prevede
- [ ] Il grafo del Cervello continua a non mostrare mai il testo di un ricordo

## Criteri di accettazione

- [ ] La migrazione sale e scende su una copia del database della casa vera
- [ ] Un archivio di backup vecchio rientra e riceve i valori predefiniti
