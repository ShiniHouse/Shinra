import uvicorn

from config.settings import settings

if __name__ == "__main__":
    print("🟣 Shinra — Assistente Domestico Intelligente")
    print(f"   Server: http://localhost:{settings.server.port}")
    print(f"   Alexa Skill Endpoint: http://localhost:{settings.server.port}/api/alexa")
    uvicorn.run(
        "server.app:app", host=settings.server.host, port=settings.server.port, reload=settings.server.debug
    )
