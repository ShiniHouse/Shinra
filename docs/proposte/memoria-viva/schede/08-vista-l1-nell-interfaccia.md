---
title: "feat(frontend): la memoria in chiaro: leggere, correggere, fissare, dimenticare"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: frontend"]
---

> **Fase B — Trasparenza.** Dipende da: API della memoria.

## Contesto

Nessuna «scatola nera»: chi abita la casa deve vedere cosa Shinra ricorda e poterlo correggere al volo.
Non serve una scheda nuova (il progetto ha appena ridotto gli ingressi da otto a tre): si estende la scheda
**Conoscenza**, che gia' elenca i fatti.

## Cosa fare

- [ ] Selettore «Casa | I miei» nella scheda Conoscenza
- [ ] Per ogni ricordo: origine, importanza, ultimo uso; modifica sul posto, «fissa» (importanza massima), archivia, elimina
- [ ] Ogni testo che finisce nella pagina passa da `_html`/`_args`; i gesti sono registrati; nessun file oltre le 500 righe
- [ ] Gli stati vuoti insegnano la mossa successiva (come nel resto della dashboard)

## Criteri di accettazione

- [ ] Prova dei gesti nel browser: modificare, fissare, eliminare un ricordo
- [ ] Un ricordo con un testo ostile (`<img onerror=...>`) resta testo, in elenco e in modifica
