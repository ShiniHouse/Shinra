"""Il punto di ingresso: `shinra` da riga di comando, o `python run.py`.

Esiste come modulo del pacchetto e non dentro `run.py` perche' l'entry point
dichiarato in `pyproject.toml` deve poter essere importato: `run.py` sta
nella radice del repository e in un'installazione non c'e'.
"""

from __future__ import annotations

import uvicorn

from shinra.config.settings import settings

SECONDI_PER_CHIUDERE = 10


def principale() -> None:
    print("🟣 Shinra — Assistente Domestico Intelligente")
    print(f"   Server: http://localhost:{settings.server.port}")
    print(f"   Endpoint della skill Alexa: http://localhost:{settings.server.port}/api/alexa")
    uvicorn.run(
        "shinra.api.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.debug,
        # Quanto si aspetta che le connessioni aperte si chiudano da sole.
        # Senza, uvicorn aspetta per sempre: basta una connessione che non
        # si accorge della chiusura e il servizio non si ferma piu'. E'
        # successo con `/ws/eventi`, che ascoltava solo cio' che doveva
        # mandare (issue #118).
        #
        # Quella rotta e' stata sistemata, e questo non serve a lei: serve
        # alla prossima. Dieci secondi sono molto piu' di quanto occorra a
        # una fermata sana — misurata in due decimi — e molto meno dei
        # novanta oltre i quali systemd manda un SIGKILL, che salta tutto
        # lo spegnimento ordinato.
        timeout_graceful_shutdown=SECONDI_PER_CHIUDERE,
    )


if __name__ == "__main__":
    principale()
