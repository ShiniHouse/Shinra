import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import reload_settings

logger = logging.getLogger(__name__)


_client_condiviso: Optional["HomeAssistantClient"] = None


def client_home_assistant() -> "HomeAssistantClient":
    """Il client condiviso dell'applicazione.

    Prima ce n'erano quattro, e uno — quello usato da tutti i tool — riceveva
    URL e token come valori al momento dell'import, congelandoli. Chi
    correggeva l'indirizzo dalle impostazioni vedeva il pannello diagnostico
    diventare verde, perche' usava un client dinamico, mentre i comandi ai
    dispositivi continuavano a fallire contro il vecchio indirizzo fino al
    riavvio.
    """
    global _client_condiviso
    if _client_condiviso is None:
        _client_condiviso = HomeAssistantClient()
    return _client_condiviso


class HomeAssistantClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self._base_url = base_url
        self._token = token
        self._http: Optional[httpx.AsyncClient] = None

    def _connessione(self, timeout: float) -> httpx.AsyncClient:
        """Riusa una sola connessione invece di aprirne una per chiamata.

        Ogni metodo apriva il proprio `httpx.AsyncClient`: una connessione TCP
        e un handshake nuovi per ogni lampadina accesa.
        """
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=timeout)
        return self._http

    async def chiudi(self) -> None:
        """Chiude la connessione. Chiamata allo spegnimento dell'applicazione."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

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
            return {"status": "unconfigured", "message": "Token non inserito", "url": curr_url}
        try:
            client = self._connessione(4.0)
            res = await client.get(f"{curr_url}/api/", headers=self.headers)
            if res.status_code == 200:
                return {"status": "ok", "message": "Connesso", "url": curr_url, "data": res.json()}
            elif res.status_code == 401:
                return {
                    "status": "unauthorized",
                    "message": "Token errato / non valido (401)",
                    "url": curr_url,
                }
            else:
                return {"status": "error", "message": f"Errore HTTP {res.status_code}", "url": curr_url}
        except httpx.ConnectError:
            return {
                "status": "unreachable",
                "message": f"IP/URL non raggiungibile ({curr_url})",
                "url": curr_url,
            }
        except httpx.TimeoutException:
            return {
                "status": "timeout",
                "message": f"Timeout di connessione verso {curr_url}",
                "url": curr_url,
            }
        except Exception as e:
            return {"status": "unreachable", "message": f"Errore: {e!s}", "url": curr_url}

    async def get_states(self) -> List[Dict[str, Any]]:
        """Recupera lo stato di tutte le entità su Home Assistant."""
        if not self.token or self.token.startswith("INSERISCI_QUI") or len(self.token) < 20:
            return []
        try:
            client = self._connessione(6.0)
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

    async def call_service(
        self, domain: str, service: str, service_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Chiama un servizio su Home Assistant (es. light.turn_on, climate.set_temperature)."""
        if not self.token or self.token.startswith("INSERISCI_QUI"):
            return {"success": False, "error": "Token Home Assistant non configurato."}
        try:
            url = f"{self.base_url}/api/services/{domain}/{service}"
            client = self._connessione(8.0)
            res = await client.post(url, headers=self.headers, json=service_data or {})
            if res.status_code == 200:
                return {"success": True, "result": res.json()}
            return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def speak_on_alexa(self, message: str, alexa_entity_id: Optional[str] = None) -> Dict[str, Any]:
        """Invia un messaggio vocale TTS su un dispositivo Echo tramite alexa_media_player."""
        target_entity = alexa_entity_id or "media_player.alexa"
        service_data = {"entity_id": target_entity, "message": message, "data": {"type": "tts"}}
        return await self.call_service("notify", "alexa_media", service_data)
