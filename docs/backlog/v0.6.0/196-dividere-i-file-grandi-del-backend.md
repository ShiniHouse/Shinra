---
title: "refactor(backend): nessun file del backend sopra le cinquecento righe, e un test a dirlo"
issue: 196
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: core"]
---

## Contesto

Nel frontend il tetto delle cinquecento righe e' gia' applicato da un test.
Nel backend tre file lo superano: `skills/registry.py` (circa 850 righe),
`api/routes_admin.py` (circa 850) e `api/app.py` (circa 700). Sono anche i
posti dove gli agenti della `0.6.0` toccheranno di piu': meglio sistemarli
prima, non dopo.

## Cosa fare

- [x] Dividere `skills/registry.py` per dominio, in modo che il registro degli agenti possa riusare la stessa scomposizione — `skills/catalogo/`, otto moduli; `registry.py` da 854 a 93 righe
- [x] Dividere `api/routes_admin.py` per area — `routes_utenti`, `routes_casa`, `routes_impostazioni`, `routes_attivita`
- [x] Portare `api/app.py` sotto il tetto — 460 righe; il ciclo di vita e' in `api/ciclo_di_vita.py`
- [x] Un test che fallisce se un file di `src/shinra/` supera il tetto, con eventuali eccezioni elencate una per una come in `test_architettura.py` — `test_dimensione_backend.py`

## Criteri di accettazione

- [x] Nessun comportamento cambia: la suite passa senza modifiche ai test funzionali — le 90 rotte, chi le puo' chiamare, i 36 schemi e i 37 gestori sono identici a prima (confrontati con un'istantanea)
- [x] Il test del tetto esiste e le eccezioni, se ce ne sono, hanno un motivo scritto
- [~] `test_architettura.py`: nessuna direzione nuova, ma le coppie file -> modulo passano da 10 a 12, perche' lo stesso accesso a `infra/` compare in piu' file piu' piccoli. Il debito resta quello, e si scioglie insieme

## Com'e' andata

- `skills/registry.py` era 710 righe di schemi piu' il codice che li esegue. Adesso
  ogni dominio ha il suo modulo in `skills/catalogo/` con due elenchi,
  `GESTORI` e `SCHEMI`; il registro li somma ed esegue. Il giorno che gli agenti
  di dominio (#190) vorranno vedere solo i propri strumenti, la divisione e'
  fatta.
- `routes_admin.py` (889 righe) e' sparito: le rotte stanno in quattro file per
  area, ciascuno con lo stesso router protetto per difetto.
- `app.py` (726 righe) ha perso il ciclo di vita (`ciclo_di_vita.py`): cosa si
  prepara all'avvio e cosa si ferma allo spegnimento.
- **Restano cinque file sopra le 500 righe**, congelati al loro massimo in
  `test_dimensione_backend.py` con il motivo: `infra/db/depositi.py` (702),
  `services/interview_engine.py` (592, lo riscrivono la #209 e la #210),
  `services/regole.py` (534), `domain/grafo.py` (520), `infra/db/modelli.py` (508).
  La scheda ne nominava tre; questi cinque non erano nel perimetro, e il test li
  tiene dal crescere. Un file in elenco che rientra nel tetto fa fallire il
  test finche' non lo si toglie: l'elenco puo' solo accorciarsi.
