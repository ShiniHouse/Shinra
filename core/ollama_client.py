import json
import logging
import re
from typing import List, Dict, Any, Optional
import httpx

from config.settings import reload_settings

logger = logging.getLogger(__name__)

# Set dei modelli che non supportano tools nativi via API Ollama
_NON_TOOL_MODELS = {"gemma", "gemma2", "gemma3", "deepseek-r1", "phi", "phi3"}

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self._base_url = base_url
        self._model = model

    @property
    def base_url(self) -> str:
        if self._base_url:
            return self._base_url.rstrip("/")
        cfg = reload_settings()
        return cfg.llm.ollama_url.rstrip("/")

    @property
    def model(self) -> str:
        if self._model:
            return self._model
        cfg = reload_settings()
        return cfg.llm.model

    @property
    def timeout(self) -> float:
        cfg = reload_settings()
        return float(cfg.llm.timeout_seconds or 180)

    async def get_available_models(self) -> List[str]:
        """Recupera la lista dei modelli installati su Ollama."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(6.0, connect=3.0)) as client:
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
        cfg = reload_settings()
        curr_model = self.model
        curr_temp = temperature if temperature is not None else cfg.llm.temperature
        url = f"{self.base_url}/api/chat"

        # Verifica se il modello è noto per non supportare tools (evita richiesta inutile che fallisce con 400)
        model_family = curr_model.split(":")[0].lower()
        supports_tools = tools and (model_family not in _NON_TOOL_MODELS) and not any(k in curr_model.lower() for k in ["gemma", "deepseek-r1", "phi"])

        max_tok = cfg.llm.max_tokens if hasattr(cfg.llm, 'max_tokens') and cfg.llm.max_tokens else 150
        payload = {
            "model": curr_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": curr_temp,
                "num_ctx": 2048 if max_tok > 250 else 1024,
                "num_predict": max_tok,
                "top_p": 0.9
            }
        }
        if supports_tools and tools:
            payload["tools"] = tools

        req_timeout = httpx.Timeout(timeout=max(self.timeout, 180.0), connect=10.0)

        try:
            async with httpx.AsyncClient(timeout=req_timeout) as client:
                res = await client.post(url, json=payload)

                # Fallback di sicurezza se un modello inatteso restituisce 'does not support tools'
                if res.status_code == 400 and "does not support tools" in res.text and "tools" in payload:
                    logger.warning(f"Il modello {curr_model} non supporta tools nativi. Retry immediato senza tools.")
                    _NON_TOOL_MODELS.add(model_family)
                    del payload["tools"]
                    res = await client.post(url, json=payload)

                if res.status_code == 200:
                    data = res.json()
                    message = data.get("message", {})
                    content = message.get("content", "") or data.get("response", "")

                    # Rimuovi eventuali tag <thought> o estrai il testo se necessario
                    if "<thought>" in content and "</thought>" in content:
                        content = re.sub(r"<thought>.*?</thought>", "", content, flags=re.DOTALL).strip()

                    return {
                        "success": True,
                        "message": message,
                        "content": content,
                        "tool_calls": message.get("tool_calls", [])
                    }
                else:
                    err_detail = res.text or f"Status {res.status_code}"
                    logger.error(f"Errore risposta Ollama {res.status_code}: {err_detail}")
                    return {
                        "success": False,
                        "error": f"Ollama HTTP {res.status_code}: {err_detail}"
                    }

        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Impossibile connettersi ad Ollama su {self.base_url}."
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"Timeout durante l'elaborazione del modello {curr_model} (tempo limite superato)."
            }
        except Exception as e:
            logger.error(f"Eccezione chiamata Ollama: {e}")
            return {
                "success": False,
                "error": str(e)
            }

