---
title: "fix(config): collegare le impostazioni esposte e mai lette"
milestone: "v0.3.0"
labels: ["tipo: difetto", "area: core", "gravita': media"]
---

## Contesto

Nove elementi che l'interfaccia o la configurazione espongono come funzionanti,
e che **nessuna riga di codice consuma**. Non producono errori: producono
silenzio, il che li rende peggiori di un difetto visibile.

| Elemento | Cosa succede davvero |
| :--- | :--- |
| `data/sources.json` | Gestore fonti RSS completo, con catalogo di venti testate e toggle di massa. `news_search.py` usa un dizionario `RSS_FEEDS` scritto nel codice e non chiama mai `get_sources()`. Disattivare ANSA Politica non cambia nulla. |
| `preferred_news_categories` | Salvato per ogni utente, mai letto. Il briefing notizie e' identico per tutti. |
| `restricted_topics` | Mai letto. Nessun filtro sui contenuti per i minori. *(Risolto in v0.1.0 dalla issue #08)* |
| `alexa.skill_id` | Mai letto. *(Risolto in v0.1.0 dalla issue #04)* |
| `alexa_media_player_entity` e `speak_on_alexa()` | La funzione e' definita in `ha_client.py` e non viene chiamata da nessuno: l'assistente non puo' parlare spontaneamente su un Echo. *(Collegato in v0.2.0 dalla issue #11)* |
| `security.session_secret` | Mai letto. *(Risolto in v0.1.0 dalla issue #06)* |
| `duckduckgo-search` | Dipendenza mai importata. *(Rimossa in v0.1.0 dalla issue #10)* |
| `memory.add_tool_interaction` | Corpo `pass`. *(Implementato in v0.2.0 dalla issue #13)* |
| Domini `lock`, `vacuum`, `fan` | Visibili e non comandabili. *(Risolto dalla issue #20)* |

Questa issue chiude i due elementi rimasti e introduce il controllo che impedisce
che il fenomeno si ripeta.

## Cosa fare

- [ ] `get_latest_news` e `search_web` leggono le fonti da database, rispettando lo stato attivo/disattivo e la categoria
- [ ] Il briefing notizie filtra su `preferred_news_categories` del profilo che ha posto la domanda
- [ ] Aggiungere un test che confronta i campi di configurazione esposti con quelli effettivamente letti dal codice, e fallisce se un campo non ha consumatori
- [ ] Rimuovere ogni opzione che non si intende collegare, invece di lasciarla esposta

## Criteri di accettazione

- [ ] Disattivare una fonte nell'interfaccia la esclude dalle notizie
- [ ] Due profili con categorie diverse ricevono notizie diverse
- [ ] Il test di coerenza della configurazione e' verde e fallisce se si aggiunge un'opzione senza consumatore
