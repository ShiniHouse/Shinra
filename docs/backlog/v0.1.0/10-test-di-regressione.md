---
title: "test: rete di regressione sui difetti della revisione tecnica"
milestone: "v0.1.0"
labels: ["tipo: attivita'", "area: infra", "gravita': alta"]
---

## Contesto

Il progetto non ha test. `test_tools.py` e' uno script di stampe che chiama API
esterne reali: non verifica nulla e non puo' girare in CI.

Entrambi i difetti bloccanti sono chiamate a metodi inesistenti: **qualsiasi
test che avesse eseguito quel percorso li avrebbe intercettati.**

## Cosa fare

- [ ] Struttura `tests/unit/` e `tests/integration/`
- [ ] Un test per ogni difetto della revisione, che fallisce prima della correzione
- [ ] Finche' un difetto e' aperto, il test porta `@pytest.mark.xfail(strict=True)`: quando la correzione arriva il test diventa rosso, obbligando a togliere il marcatore. Nessun difetto puo' essere dichiarato risolto senza prova.
- [ ] Test degli endpoint con `TestClient`, per verificare le protezioni di SEC-01
- [ ] Simulare le chiamate HTTP con `respx`: nessuna rete nei test unitari
- [ ] Convertire `test_tools.py` in test veri, marcati `network`
- [ ] Test del parser dei timer, che e' pura logica e oggi non e' coperto
- [ ] Rimuovere `duckduckgo-search` da `requirements.txt`: non e' importato da nessuna parte

## Criteri di accettazione

- [ ] `pytest -m "not network and not integration"` e' verde e non tocca la rete
- [ ] Ogni difetto della revisione ha un test corrispondente
- [ ] La CI esegue i test su Python 3.10, 3.11 e 3.12
- [ ] Il tempo di esecuzione della suite resta sotto i trenta secondi
