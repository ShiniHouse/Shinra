---
title: "fix(config): collegare le impostazioni esposte e mai lette"
issue: 26
milestone: "v0.3.0"
labels: ["tipo: difetto", "area: core", "gravita': media"]
---

## Contesto

Nove elementi che l'interfaccia o la configurazione espongono come funzionanti,
e che **nessuna riga di codice consuma**. Non producono errori: producono
silenzio, il che li rende peggiori di un difetto visibile.

| Elemento | Cosa succede davvero |
| :--- | :--- |
| `data/sources.json` | Gestore fonti RSS completo, con catalogo di venti testate e toggle di massa. `news_search.py` usava un dizionario scritto nel codice e non chiamava mai `get_sources()`. Disattivare ANSA Politica non cambiava nulla. *(Risolto da questa issue)* |
| `preferred_news_categories` | Salvato per ogni utente, mai letto. Il briefing notizie era identico per tutti. *(Risolto da questa issue)* |
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

- [x] `get_latest_news` legge le fonti dal database, rispettando lo stato
      attivo/disattivo e la categoria. `search_web` **no, e non deve**: e' una
      ricerca su una domanda libera, non la lettura di un feed, e non c'e'
      niente da filtrare. Fingere il contrario avrebbe aggiunto un'altra
      opzione senza effetto, che e' il difetto che questa scheda chiude
- [x] Il briefing notizie filtra su `preferred_news_categories` del profilo che ha posto la domanda
- [x] Il test c'e' (`test_ogni_opzione_di_configurazione_ha_un_consumatore`) e alla
      prima esecuzione ha trovato due opzioni che nessun elenco scritto a mano
      aveva notato: `assistant.language` e `security.protect_dashboard`
- [x] Tolte tutte e due. `assistant.language` tornera' con la
      internazionalizzazione (issue #36), che e' il lavoro che la rende vera.
      `security.protect_dashboard` aveva perfino una casella nelle
      impostazioni mentre la rotta rispondeva `True` fisso: prometteva di
      poter *disattivare* la protezione della dashboard, cioe' di riaprire il
      difetto SEC-03 chiuso nella v0.1.0. Un'opzione del genere non va
      collegata, va tolta

## Criteri di accettazione

- [x] Disattivare una fonte nell'interfaccia la esclude dalle notizie
- [x] Due profili con categorie diverse ricevono notizie diverse
- [x] Il test di coerenza e' verde e fallisce se si aggiunge un'opzione senza
      consumatore — verificato aggiungendone una finta
