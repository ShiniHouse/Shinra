"""Il punto di ingresso: `shinra` da riga di comando, o `python run.py`.

Esiste come modulo del pacchetto e non dentro `run.py` perche' l'entry point
dichiarato in `pyproject.toml` deve poter essere importato: `run.py` sta
nella radice del repository e in un'installazione non c'e'.
"""

from __future__ import annotations

import uvicorn

from shinra.config.settings import settings


def principale() -> None:
    print("🟣 Shinra — Assistente Domestico Intelligente")
    print(f"   Server: http://localhost:{settings.server.port}")
    print(f"   Endpoint della skill Alexa: http://localhost:{settings.server.port}/api/alexa")
    uvicorn.run(
        "shinra.api.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.debug,
    )


if __name__ == "__main__":
    principale()
