"""Dove si trova una persona, rispetto ai luoghi registrati (#343).

La posizione e' un dato delicato e questo modulo ne tiene tre regole, difese dai test:

- **si legge al momento e non si conserva**: nessuna tabella di posizioni, nessuna traccia degli spostamenti. Si guarda
  l'ultimo stato che Home Assistant ha mandato (la cache), oppure l'ultima posizione che l'app Shinra installata sul telefono
  ha segnalato (solo in memoria, persa al riavvio), e si confronta con i luoghi;
- **solo chi l'ha acceso e' localizzato**: un profilo senza `entita_posizione` non ha una posizione, e dirlo e' la risposta;
- **si risponde col nome del luogo, mai con le coordinate**: le coordinate non escono da qui.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from shinra.domain import luoghi as dominio
from shinra.infra.db import depositi
from shinra.infra.homeassistant.stati import cache_stati
from shinra.services import luoghi, registro

# Quanto puo' essere vecchia una posizione per valere ancora. Un telefono fermo non manda aggiornamenti: chi sta otto ore al
# lavoro ha una posizione «vecchia» di otto ore che e' giustissima. Si scarta solo oltre mezza giornata (telefono spento, app
# chiusa da ieri), e comunque si dice **quanto** e' vecchia.
VALIDITA_SECONDI = 12 * 3600

# La fonte «questa app»: la posizione la manda il telefono con l'app Shinra aperta (GPS dell'iPhone), senza passare da Home
# Assistant. Su iPhone una web app legge la posizione **solo mentre e' aperta**: una segnalazione vale poco, venti minuti.
DISPOSITIVO = "dispositivo"
VALIDITA_APP_SECONDI = 20 * 60

SPENTA = "spenta"
IGNOTA = "ignota"
IN_UN_LUOGO = "in_un_luogo"
IN_GIRO = "in_giro"

# Perche' non si sa dove e': detto a chi chiede, cosi' sa cosa guardare.
NON_E_IN_HOME_ASSISTANT = "non_in_home_assistant"
APP_SENZA_SEGNALAZIONE = "app_senza_segnalazione"
SENZA_COORDINATE = "senza_coordinate"
TROPPO_VECCHIA = "troppo_vecchia"
COORDINATE_ILLEGGIBILI = "coordinate_illeggibili"


@dataclass(frozen=True)
class DoveSei:
    stato: str
    luogo: Optional[str] = None
    tipo: Optional[str] = None
    principale: bool = False
    # Per spiegare un «non so» o un «in giro»: mai le coordinate, solo cose che aiutano a capire cosa non va.
    motivo: Optional[str] = None
    vicino: Optional[str] = None
    distanza_m: Optional[int] = None
    eta_minuti: Optional[int] = None

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "stato": self.stato,
            "luogo": self.luogo,
            "tipo": self.tipo,
            "principale": self.principale,
            "motivo": self.motivo,
            "vicino": self.vicino,
            "distanza_m": self.distanza_m,
            "eta_minuti": self.eta_minuti,
        }


def _eta_secondi(stato: dict[str, Any], adesso: float) -> Optional[float]:
    """Da quanto tempo l'ultimo aggiornamento della posizione, se Home Assistant lo dice."""
    scritto = stato.get("last_updated") or stato.get("last_changed")
    if not scritto:
        return None
    try:
        quando = datetime.fromisoformat(str(scritto).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, adesso - quando.timestamp())


_dall_app: dict[str, tuple[float, float, Optional[int], float]] = {}


def segnala(
    profilo_id: str,
    latitudine: Any,
    longitudine: Any,
    precisione_m: Any = None,
    adesso: Optional[float] = None,
) -> None:
    """L'app Shinra del telefono dice dove si trova. Si tiene **in memoria**, una sola posizione per profilo: niente tabella."""
    r = dominio.valida(
        {
            "nome": "x",
            "latitudine": latitudine,
            "longitudine": longitudine,
            "origine": "telefono",
            "precisione_m": precisione_m,
        }
    )
    _dall_app[profilo_id] = (
        r.latitudine,
        r.longitudine,
        r.precisione_m,
        time.time() if adesso is None else adesso,
    )


def dimentica_segnalazione(profilo_id: str) -> None:
    _dall_app.pop(profilo_id, None)


def _dal_punto(punto: tuple[float, float], eta_minuti: Optional[int]) -> DoveSei:
    """Il luogo registrato che contiene il punto, o «in giro» col piu' vicino e a quanto."""
    registrati = luoghi.elenco()
    luogo = dominio.piu_vicino(punto[0], punto[1], registrati)
    if luogo is not None:
        return DoveSei(
            IN_UN_LUOGO,
            str(luogo["nome"]),
            str(luogo["tipo"]),
            bool(luogo["principale"]),
            eta_minuti=eta_minuti,
        )

    # In giro: il piu' vicino e a quanto, arrotondato a cento metri. Aiuta a capire se il luogo e' stato registrato male
    # (una posizione presa da un PC puo' sbagliare di chilometri) senza dire dove si e'.
    vicino, distanza = None, None
    for x in registrati:
        d = dominio.distanza_m(punto[0], punto[1], float(x["latitudine"]), float(x["longitudine"]))
        if distanza is None or d < distanza:
            vicino, distanza = str(x["nome"]), d
    arrotondata = None if distanza is None else int(round(distanza / 100.0) * 100)
    return DoveSei(IN_GIRO, vicino=vicino, distanza_m=arrotondata, eta_minuti=eta_minuti)


def dove_sei(entita_posizione: str, adesso: Optional[float] = None, profilo_id: str = "") -> DoveSei:
    """In quale luogo registrato si trova la persona collegata a `entita_posizione` (un'entita' di Home Assistant o l'app)."""
    if not entita_posizione:
        return DoveSei(SPENTA)

    ora = time.time() if adesso is None else adesso

    if entita_posizione == DISPOSITIVO:
        segnalata = _dall_app.get(profilo_id)
        if segnalata is None:
            return DoveSei(IGNOTA, motivo=APP_SENZA_SEGNALAZIONE)
        s_lat, s_lon, _, quando = segnalata
        eta = max(0.0, ora - quando)
        if eta > VALIDITA_APP_SECONDI:
            return DoveSei(IGNOTA, motivo=TROPPO_VECCHIA, eta_minuti=int(eta // 60))
        return _dal_punto((s_lat, s_lon), int(eta // 60))

    stato = cache_stati.stato(entita_posizione)
    if not stato:
        return DoveSei(IGNOTA, motivo=NON_E_IN_HOME_ASSISTANT)

    eta_s = _eta_secondi(stato, ora)
    eta_minuti = None if eta_s is None else int(eta_s // 60)
    if eta_s is not None and eta_s > VALIDITA_SECONDI:
        return DoveSei(IGNOTA, motivo=TROPPO_VECCHIA, eta_minuti=eta_minuti)

    attributi = stato.get("attributes") or {}
    lat, lon = attributi.get("latitude"), attributi.get("longitude")
    if lat is None or lon is None:
        return DoveSei(IGNOTA, motivo=SENZA_COORDINATE, eta_minuti=eta_minuti)
    try:
        punto = (float(lat), float(lon))
    except (TypeError, ValueError):
        return DoveSei(IGNOTA, motivo=COORDINATE_ILLEGGIBILI, eta_minuti=eta_minuti)
    return _dal_punto(punto, eta_minuti)


def luogo_attuale(entita_posizione: str, profilo_id: str = "") -> Optional[dict[str, Any]]:
    """Il luogo registrato in cui si trova la persona, **con le coordinate**: per uso interno (il meteo), mai da mostrare."""
    risposta = dove_sei(entita_posizione, profilo_id=profilo_id)
    if risposta.stato != IN_UN_LUOGO:
        return None
    return next((x for x in luoghi.elenco() if x["nome"] == risposta.luogo), None)


def luogo_dallo_stato(stato: str) -> str:
    """L'identificativo del luogo registrato che corrisponde allo stato di una persona di Home Assistant, o vuoto.

    Home Assistant dice dove e' una persona con il **nome della zona** in cui si trova (`home` per la zona di casa, altrimenti
    il nome della zona) oppure `not_home`. Si riusano le zone che Home Assistant gia' conosce: nessuna coordinata, nessuna
    traccia di spostamenti. `home` vale per il luogo principale; gli altri si riconoscono dal nome, senza badare alle maiuscole.
    """
    pulito = " ".join(str(stato or "").split()).casefold()
    if not pulito or pulito in ("not_home", "unknown", "unavailable"):
        return ""
    if pulito == "home":
        principale = luoghi.principale()
        return str(principale["id"]) if principale else ""
    for x in luoghi.elenco():
        if " ".join(str(x["nome"]).split()).casefold() == pulito:
            return str(x["id"])
    return ""


def zona_di_home_assistant(nome_luogo: str, principale: bool) -> bool:
    """Se Home Assistant ha una zona che corrisponde a questo luogo: `home` per il principale, altrimenti una `zone.*` con quel nome."""
    if principale and cache_stati.stato("zone.home") is not None:
        return True
    voluto = " ".join(str(nome_luogo).split()).casefold()
    for stato in cache_stati.tutti():
        if not str(stato.get("entity_id", "")).startswith("zone."):
            continue
        nome = (stato.get("attributes") or {}).get("friendly_name") or ""
        if " ".join(str(nome).split()).casefold() == voluto:
            return True
    return False


def luogo_del_discorso(testo: str, profilo: Any = None) -> Optional[dict[str, Any]]:
    """Il luogo di cui si sta parlando: quello nominato nella frase, poi dove si trova chi parla, poi la casa principale.

    Serve a scegliere quali ricordi mettere nel prompt (#345). Le coordinate restano qui dentro: chi chiama usa il nome o
    l'identificativo.
    """
    nominato = luoghi.nominato_nella_frase(testo)
    if nominato is not None:
        return nominato
    entita = getattr(profilo, "entita_posizione", "") or ""
    if entita:
        attuale = luogo_attuale(entita, getattr(profilo, "id", "") or "")
        if attuale is not None:
            return attuale
    return luoghi.principale()


PREFISSI_AMMESSI = ("person.", "device_tracker.")


class EntitaNonValida(ValueError):
    pass


def collega(profilo_id: str, entita: str) -> DoveSei:
    """Collega la persona o il telefono di Home Assistant a un profilo (vuoto: spegne la posizione).

    Si salva il **nome dell'entita'**, mai dove si trova la persona. Il registro scrive chi ha acceso o spento, non dove e'.
    """
    entita = (entita or "").strip()
    if entita and entita != DISPOSITIVO and not entita.startswith(PREFISSI_AMMESSI):
        raise EntitaNonValida(
            "Serve una persona o un telefono di Home Assistant (person.… o device_tracker.…), oppure questa app."
        )
    # Cambiando fonte o spegnendo, l'ultima posizione segnalata dall'app non vale piu'.
    dimentica_segnalazione(profilo_id)
    from shinra.services import posizione_eventi

    posizione_eventi.dimentica(profilo_id)
    depositi.utenti.aggiorna(profilo_id, {"entita_posizione": entita})
    registro.registra(
        "posizione.collegata" if entita else "posizione.spenta", dettagli={"profilo": profilo_id}
    )
    return dove_sei(entita, profilo_id=profilo_id)


def candidati() -> list[dict[str, Any]]:
    """Le persone e i telefoni di Home Assistant fra cui scegliere, col nome che si legge.

    Chi collega la propria posizione non conosce `device_tracker.iphone_di_mario`: conosce «iPhone di Mario». Si elencano
    quelli che hanno gia' una posizione (latitudine e longitudine) prima, poi le persone. In testa, sempre, «questo telefono»:
    la posizione la manda l'app Shinra. Le coordinate non escono.
    """
    trovati: list[dict[str, Any]] = []
    for stato in cache_stati.tutti():
        identificativo = str(stato.get("entity_id", ""))
        if not identificativo.startswith(PREFISSI_AMMESSI):
            continue
        attributi = stato.get("attributes") or {}
        trovati.append(
            {
                "entita": identificativo,
                "nome": str(attributi.get("friendly_name") or identificativo),
                "persona": identificativo.startswith("person."),
                "ha_posizione": attributi.get("latitude") is not None
                and attributi.get("longitude") is not None,
            }
        )
    ordinati = sorted(
        trovati, key=lambda c: (not c["ha_posizione"], not c["persona"], str(c["nome"]).lower())
    )
    questa_app = {
        "entita": DISPOSITIVO,
        "nome": "Questo telefono (app Shinra, solo quando è aperta)",
        "persona": False,
        "ha_posizione": True,
    }
    return [questa_app, *ordinati]
