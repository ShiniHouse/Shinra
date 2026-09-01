import httpx
import logging
from typing import Any, Dict, List, Optional
from config.settings import reload_settings

logger = logging.getLogger(__name__)

class HomeAssistantClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self._base_url = base_url
        self._token = token

    @property
    def base_url(self) -> str:
        if self._base_url:
            return self._base_url.rstrip("/")
        cfg = reload_settings()
        return cfg.home_assistant.url.rstrip("/")

    @property
    def token(self) -> str:
        if self._token:
            return self._token
        cfg = reload_settings()
        return cfg.home_assistant.token

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def check_connection(self) -> Dict[str, Any]:
        """Verifica se il server Home Assistant è raggiungibile e il token è valido."""
        curr_token = self.token
        curr_url = self.base_url

        if not curr_token or curr_token.startswith("INSERISCI_QUI") or len(curr_token) < 20:
            return {
                "status": "unconfigured",
                "message": "Token non inserito",
                "url": curr_url
            }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{curr_url}/api/", headers=self.headers)
                if res.status_code == 200:
                    return {
                        "status": "ok",
                        "message": "Connesso",
                        "url": curr_url,
                        "data": res.json()
                    }
                elif res.status_code == 401:
                    return {
                        "status": "unauthorized",
                        "message": "Token errato / non valido (401)",
                        "url": curr_url
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Errore HTTP {res.status_code}",
                        "url": curr_url
                    }
        except httpx.ConnectError:
            return {
                "status": "unreachable",
                "message": f"IP/URL non raggiungibile ({curr_url})",
                "url": curr_url
            }
        except httpx.TimeoutException:
            return {
                "status": "timeout",
                "message": f"Timeout di connessione verso {curr_url}",
                "url": curr_url
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "message": f"Errore: {str(e)}",
                "url": curr_url
            }

    async def get_states(self) -> List[Dict[str, Any]]:
        """Recupera lo stato di tutte le entità su Home Assistant."""
        if not self.token or self.token.startswith("INSERISCI_QUI") or len(self.token) < 20:
            return []
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(f"{self.base_url}/api/states", headers=self.headers)
                if res.status_code == 200:
                    return res.json()
                logger.error(f"Errore recupero stati HA: {res.status_code} - {res.text}")
                return []
        except Exception as e:
            logger.error(f"Eccezione recupero stati HA: {e}")
            return []

    async def get_relevant_entities_summary(self) -> str:
        """Restituisce un riassunto sintetico e veloce delle entità controllabili principali."""
        states = await self.get_states()
        if not states:
            return ""

        controllable_domains = {"light", "switch", "climate", "cover", "media_player"}
        summary_lines = []

        for entity in states:
            entity_id = entity.get("entity_id", "")
            domain = entity_id.split(".")[0]
            if domain in controllable_domains:
                friendly_name = entity.get("attributes", {}).get("friendly_name", entity_id)
                state = entity.get("state", "unknown")
                if state not in ("unavailable", "unknown"):
                    summary_lines.append(f"{friendly_name} ({entity_id}): {state}")

        return "; ".join(summary_lines[:15])

    async def call_service(self, domain: str, service: str, service_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Chiama un servizio su Home Assistant (es. light.turn_on, climate.set_temperature)."""
        if not self.token or self.token.startswith("INSERISCI_QUI"):
            return {"success": False, "error": "Token Home Assistant non configurato."}
        try:
            url = f"{self.base_url}/api/services/{domain}/{service}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, headers=self.headers, json=service_data or {})
                if res.status_code == 200:
                    return {"success": True, "result": res.json()}
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def speak_on_alexa(self, message: str, alexa_entity_id: Optional[str] = None) -> Dict[str, Any]:
        """Invia un messaggio vocale TTS su un dispositivo Echo tramite alexa_media_player."""
        target_entity = alexa_entity_id or "media_player.alexa"
        service_data = {
            "entity_id": target_entity,
            "message": message,
            "data": {"type": "tts"}
        }
        return await self.call_service("notify", "alexa_media", service_data)
