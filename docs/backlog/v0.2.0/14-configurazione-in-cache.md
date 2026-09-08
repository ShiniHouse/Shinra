---
title: "perf(config): configurazione in cache con invalidazione al salvataggio"
issue: 14
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

- [x] Caricare la configurazione una volta all'avvio e tenerla in memoria
- [x] Invalidare la cache esplicitamente al salvataggio delle impostazioni,
      notificando i componenti interessati. Non serve una notifica: dalla
      correzione di `reload_settings()` (PR #61) esiste un solo oggetto
      condiviso, aggiornato al suo posto. Chi lo legge vede subito il valore
      nuovo, e non c'e' una cache da invalidare che qualcuno possa scordarsi.
- [ ] ~~Passare a `pydantic-settings`~~ — **non fatto, di proposito.** La
      precedenza richiesta (ambiente, poi `.env`, poi `config.yaml`, poi i
      valori predefiniti) esiste gia' in `config/secrets.py` ed e' coperta da
      test. Riscriverla con un'altra libreria cambierebbe il meccanismo senza
      cambiare il comportamento: rischio senza guadagno, proprio nel punto
      dove passano i segreti di casa. Se un giorno servira' per altro, si
      riapre.
- [x] Nessuna lettura da disco durante il ciclo di vita di una richiesta

## Criteri di accettazione

- [x] Nessuna operazione di IO sincrona nel percorso di una richiesta di chat
      (misurato: cinque letture di config.yaml prima, zero dopo)
- [x] Salvare le impostazioni ha effetto immediato su tutti i componenti
- [x] Le variabili d'ambiente hanno la precedenza sul file di configurazione
      (gia' vero dalla v0.1.0, test in `tests/unit/test_segreti.py`)
