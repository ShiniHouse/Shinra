import json
import logging
import re
from typing import List, Dict, Any, Optional
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.llm.ollama_url).rstrip("/")
        self.model = model or settings.llm.model
        self.timeout = settings.llm.timeout_seconds

    async def get_available_models(self) -> List[str]:
        """Recupera la lista dei modelli installati su Ollama."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return models
                return []
        except Exception as e:
            logger.warning(f"Impossibile contattare Ollama su {self.base_url}: {e}")
            return []

    async def check_health(self) -> Dict[str, Any]:
        """Verifica se Ollama è raggiungibile e quali modelli sono pronti."""
        models = await self.get_available_models()
        if models:
            # Se il modello configurato non è presente, suggeriamo il primo disponibile o un gemma
            selected_model = self.model
            if self.model not in models:
                gemma_models = [m for m in models if "gemma" in m.lower()]
                if gemma_models:
                    selected_model = gemma_models[0]
                else:
                    selected_model = models[0]
            return {
                "status": "online",
                "available_models": models,
                "active_model": selected_model
            }
        return {
            "status": "offline",
            "message": f"Ollama non risponde su {self.base_url}. Assicurati che il servizio Ollama sia avviato.",
            "available_models": [],
            "active_model": self.model
        }

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Invia una richiesta di chat a Ollama supportando il passaggio dei tools.
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else settings.llm.temperature
            }
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    message = data.get("message", {})
                    return {
                        "success": True,
                        "message": message,
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls", [])
                    }
                else:
                    logger.error(f"Errore risposta Ollama {res.status_code}: {res.text}")
                    return {
                        "success": False,
                        "error": f"Ollama HTTP {res.status_code}: {res.text}"
                    }
        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Impossibile connettersi ad Ollama su {self.base_url}. Verifica che Ollama sia in esecuzione sul tuo PC."
            }
        except Exception as e:
            logger.error(f"Eccezione chiamata Ollama: {e}")
            return {
                "success": False,
                "error": str(e)
            }
