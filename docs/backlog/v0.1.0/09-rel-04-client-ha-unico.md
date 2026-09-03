---
title: "fix(home-assistant): un unico client, con configurazione dinamica"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: core", "area: integrazioni", "gravita': alta"]
riferimento: REL-04
---

## Contesto

`core/tools/ha_tools.py:10` istanzia il client all'import passando i valori:

```python
ha_client = HomeAssistantClient(
    base_url=settings.home_assistant.url,
    token=settings.home_assistant.token,
)
```

Passare i valori esplicitamente **congela** URL e token al momento dell'import,
perche' le property restituiscono `self._base_url` se valorizzato. Ogni altro
punto del progetto costruisce invece `HomeAssistantClient()` senza argomenti,
usando le property dinamiche.

Conseguenza: chi corregge URL o token dalle impostazioni vede il pannello
diagnostico diventare verde — usa il client dinamico — **mentre i comandi ai
dispositivi continuano a fallire** contro il vecchio indirizzo, fino al riavvio.

## Cosa fare

- [ ] Un solo client Home Assistant condiviso, fornito per iniezione di dipendenza
- [ ] Nessuna istanza creata a livello di modulo con valori congelati
- [ ] Il client riusa una singola `httpx.AsyncClient` con pool di connessioni, invece di aprirne una nuova a ogni chiamata
- [ ] Alla modifica delle impostazioni il client aggiorna URL e token senza riavvio
- [ ] Chiusura pulita del client alla terminazione dell'applicazione

## Criteri di accettazione

- [ ] Cambiare l'URL di Home Assistant dalle impostazioni ha effetto immediato sui comandi ai dispositivi, senza riavviare il servizio
- [ ] Non esistono piu' istanze di `HomeAssistantClient` create a livello di modulo
- [ ] Esiste un test che verifica la propagazione del cambio di configurazione
