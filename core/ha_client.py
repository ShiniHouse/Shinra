import httpx
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class HomeAssistantClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def check_connection(self) -> Dict[str, Any]:
        """Verifica se il server Home Assistant è raggiungibile e il token è valido."""
        if not self.token or self.token.startswith("INSERISCI_QUI"):
            return {"status": "unconfigured", "message": "Token Home Assistant non impostato"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/", headers=self.headers)
                if res.status_code == 200:
                    return {"status": "ok", "message": "Connesso a Home Assistant", "data": res.json()}
                elif res.status_code == 401:
                    return {"status": "unauthorized", "message": "Token Home Assistant non valido (401)"}
                else:
                    return {"status": "error", "message": f"Errore HTTP {res.status_code}"}
        except Exception as e:
            return {"status": "unreachable", "message": f"Home Assistant non raggiungibile ({str(e)})"}

    async def get_states(self) -> List[Dict[str, Any]]:
        """Recupera lo stato di tutte le entità su Home Assistant."""
        if not self.token or self.token.startswith("INSERISCI_QUI"):
            return []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(f"{self.base_url}/api/states", headers=self.headers)
                if res.status_code == 200:
                    return res.json()
                logger.error(f"Errore recupero stati HA: {res.status_code} - {res.text}")
                return []
        except Exception as e:
            logger.error(f"Eccezione recupero stati HA: {e}")
            return []

    async def get_relevant_entities_summary(self) -> str:
        """Restituisce un riassunto testuale sintetico delle entità rilevanti (luci, clima, sensori, switch) per il prompt di Gemma."""
        states = await self.get_states()
        if not states:
            return "Nessuna entità Home Assistant rilevata (controlla connessione e token)."

        domains_of_interest = {"light", "switch", "climate", "cover", "sensor", "media_player", "scene", "script"}
        summary_lines = []

        for entity in states:
            entity_id = entity.get("entity_id", "")
            domain = entity_id.split(".")[0]
            if domain in domains_of_interest:
                friendly_name = entity.get("attributes", {}).get("friendly_name", entity_id)
                state = entity.get("state", "unknown")
                unit = entity.get("attributes", {}).get("unit_of_measurement", "")
                
                # Ignora sensori di diagnostica troppo specifici o poco utili per il parlato
                if domain == "sensor" and any(x in entity_id for x in ["uptime", "ip_address", "last_boot"]):
                    continue

                if unit:
                    summary_lines.append(f"- {friendly_name} (`{entity_id}`): {state} {unit}")
                else:
                    summary_lines.append(f"- {friendly_name} (`{entity_id}`): {state}")

        # Limita alle prime 60 entità per non saturare il context window
        return "\n".join(summary_lines[:60])

    async def call_service(self, domain: str, service: str, service_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Chiama un servizio su Home Assistant (es. light.turn_on, climate.set_temperature)."""
        if not self.token or self.token.startswith("INSERISCI_QUI"):
            return {"success": False, "error": "Token Home Assistant non configurato."}
        try:
            url = f"{self.base_url}/api/services/{domain}/{service}"
            async with httpx.AsyncClient(timeout=10.0) as client:
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
