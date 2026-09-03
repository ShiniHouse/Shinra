---
title: "perf(config): configurazione in cache con invalidazione al salvataggio"
milestone: "v0.2.0"
labels: ["tipo: attivita'", "area: infra", "gravita': media"]
riferimento: REL-06
---

## Contesto

`reload_settings()` apre e analizza `config.yaml` **dentro** le property
`base_url`, `model`, `timeout` (`core/ollama_client.py`) e `token`, `headers`
(`core/ha_client.py`). Un singolo turno di chat produce decine di letture
sincrone dal filesystem **all'interno dell'event loop asincrono**.

Non e' percepibile su un SSD, ma e' esattamente il tipo di blocco che degrada
tutto quando il carico cresce, ed e' invisibile finche' non lo si cerca.

## Cosa fare

- [ ] Caricare la configurazione una volta all'avvio e tenerla in memoria
- [ ] Invalidare la cache esplicitamente al salvataggio delle impostazioni, notificando i componenti interessati
- [ ] Passare a `pydantic-settings`, con precedenza: variabili d'ambiente, poi `.env`, poi `config.yaml`, poi valori predefiniti
- [ ] Nessuna lettura da disco durante il ciclo di vita di una richiesta

## Criteri di accettazione

- [ ] Nessuna operazione di IO sincrona nel percorso di una richiesta di chat
- [ ] Salvare le impostazioni ha effetto immediato su tutti i componenti
- [ ] Le variabili d'ambiente hanno la precedenza sul file di configurazione
