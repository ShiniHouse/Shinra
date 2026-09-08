"""L'allarme, e le finestre che si dimentica di chiudere.

E' il dominio per cui una famiglia installa la domotica, ed era l'unico
completamente scoperto: nessun tool sapeva armare, disarmare, ne' dire se le
finestre fossero chiuse.

Tre scelte che contano piu' del codice che le esegue.

**Armare con una finestra aperta non si fa in silenzio.** L'allarme suonerebbe
da solo dopo dieci minuti, e chi lo ha armato imparerebbe la cosa sbagliata —
che l'allarme e' inaffidabile — e smetterebbe di usarlo. Meglio rifiutare e
dire quale finestra.

**Il disarmo non passa da un canale non autenticato.** E dalla voce chiede
una conferma in piu': e' cio' che chiede la scheda, ma va detto il suo limite,
perche' una conferma parlata non protegge da chi e' gia' nella stanza a
parlare. La protezione vera e' il codice dell'allarme, che si puo' passare e
che Home Assistant verifica.

**Un sensore che non risponde non e' una finestra chiusa.** Ma nemmeno una
aperta: resta fuori dal conto, altrimenti un guasto impedirebbe per sempre di
armare.

Riferimento: issue #23, ADR 0004.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from shinra.domain import aperture as dominio
from shinra.domain.contesto import CANALE_ALEXA, canale_corrente
from shinra.skills.entita import EntitaSconosciuta, nome_di, stati_noti, stato_di, verifica

logger = logging.getLogger("Shinra.SicurezzaCasa")

DOMINIO = "alarm_control_panel"

SERVIZI = {
    "arma_casa": "alarm_arm_home",
    "arma_in_casa": "alarm_arm_home",
    "arma_fuori": "alarm_arm_away",
    "arma_fuori_casa": "alarm_arm_away",
    "arma": "alarm_arm_away",
    "disarma": "alarm_disarm",
}

ARMAMENTI = frozenset({"alarm_arm_home", "alarm_arm_away"})

STATI_LEGGIBILI = {
    "disarmed": "disinserito",
    "armed_home": "inserito in casa",
    "armed_away": "inserito fuori casa",
    "arming": "in inserimento",
    "pending": "in attesa",
    "triggered": "in allarme",
}

# Quanto resta valida una richiesta di disarmo in attesa di conferma.
ATTESA_CONFERMA = 60.0
_disarmi_in_attesa: Dict[str, float] = {}


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


async def _chiama(servizio: str, dati: Dict[str, Any]) -> Dict[str, Any]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return await client_home_assistant().call_service(DOMINIO, servizio, dati)


async def stato_aperture() -> Dict[str, Any]:
    """«Sono chiuse tutte le finestre?», con l'elenco vero."""
    stati = await stati_noti()
    if not stati:
        return _fallito("Non riesco a leggere lo stato della casa in questo momento.")

    tutte = dominio.aperture(stati)
    if not tutte:
        return _fallito(
            "Non trovo sensori di porte o finestre in Home Assistant: non posso dirti se sono chiuse."
        )

    aperte = [a for a in tutte if a.aperta]
    if not aperte:
        return _riuscito(
            f"Tutto chiuso: ho controllato {len(tutte)} fra porte, finestre e tapparelle.",
            aperte=[],
            controllate=len(tutte),
        )

    return _riuscito(
        f"Risulta aperto: {dominio.riassunto(aperte)}.",
        aperte=[{"entity_id": a.entity_id, "nome": a.nome, "tipo": a.tipo} for a in aperte],
        controllate=len(tutte),
    )


async def comanda_allarme(
    azione: str,
    entity_id: str = "",
    codice: Optional[str] = None,
    forza: bool = False,
) -> Dict[str, Any]:
    """Arma, disarma o riferisce lo stato dell'allarme.

    Il permesso `sicurezza.comanda` lo impone il client di Home Assistant su
    ogni chiamata: qui non serve ricordarsene.
    """
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    pannelli = [s["entity_id"] for s in stati if str(s.get("entity_id", "")).startswith(f"{DOMINIO}.")]
    if not entity_id:
        if not pannelli:
            return _fallito("Non trovo nessuna centrale di allarme in Home Assistant.")
        if len(pannelli) > 1:
            return _fallito("In casa ci sono piu' centrali di allarme: dimmi quale. " + ", ".join(pannelli))
        entity_id = pannelli[0]

    try:
        entita = await verifica(entity_id, {DOMINIO}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)
    corrente = stato_di(entita, stati)

    if azione in ("stato", "verifica", ""):
        return _riuscito(f"{nome}: {STATI_LEGGIBILI.get(corrente, corrente)}.", stato=corrente)

    servizio = SERVIZI.get(azione)
    if not servizio:
        return _fallito(f"Azione «{azione}» non prevista per l'allarme.")

    if servizio in ARMAMENTI:
        return await _arma(entita, nome, servizio, codice, forza, stati)
    return await _disarma(entita, nome, codice)


async def _arma(
    entita: str,
    nome: str,
    servizio: str,
    codice: Optional[str],
    forza: bool,
    stati: list,
) -> Dict[str, Any]:
    aperte = dominio.aperte(stati)
    if aperte and not forza:
        # Non e' pignoleria: un allarme armato su una casa aperta suona da
        # solo, e chi lo ha armato conclude che l'allarme e' inaffidabile.
        return _fallito(
            f"Non armo {nome}: risulta aperto {dominio.riassunto(aperte)}. "
            "Chiudi, oppure dimmi di armare lo stesso.",
            aperte=[{"entity_id": a.entity_id, "nome": a.nome} for a in aperte],
            serve_conferma=True,
        )

    dati: Dict[str, Any] = {"entity_id": entita}
    if codice:
        dati["code"] = codice

    esito = await _chiama(servizio, dati)
    if not esito.get("success"):
        return _fallito(f"Non sono riuscito ad armare {nome}.")

    dove = "in casa" if servizio == "alarm_arm_home" else "fuori casa"
    if aperte:
        return _riuscito(f"{nome} inserito {dove}, ma resta aperto {dominio.riassunto(aperte)}.")
    return _riuscito(f"{nome} inserito {dove}.")


async def _disarma(entita: str, nome: str, codice: Optional[str]) -> Dict[str, Any]:
    canale = canale_corrente()

    # La scheda chiede una conferma aggiuntiva da Alexa, e questa la
    # implementa. Ma il limite va scritto dove si legge il codice: una
    # conferma parlata non protegge da chi e' gia' dentro casa a parlare —
    # e' un attrito contro il fraintendimento, non contro un intruso. Contro
    # quello c'e' il codice dell'allarme, che Home Assistant verifica.
    if canale == CANALE_ALEXA:
        adesso = time.monotonic()
        if _disarmi_in_attesa.get(entita, 0.0) < adesso:
            _disarmi_in_attesa[entita] = adesso + ATTESA_CONFERMA
            return _fallito(
                f"Sto per disinserire {nome}. Confermi? Ripeti la richiesta entro un minuto.",
                conferma_richiesta=True,
            )
        _disarmi_in_attesa.pop(entita, None)

    dati: Dict[str, Any] = {"entity_id": entita}
    if codice:
        dati["code"] = codice

    esito = await _chiama("alarm_disarm", dati)
    if not esito.get("success"):
        return _fallito(
            f"Non sono riuscito a disinserire {nome}. " "Se la centrale richiede un codice, va indicato."
        )
    logger.warning("Allarme disinserito: %s (canale %s)", entita, canale or "non indicato")
    return _riuscito(f"{nome} disinserito.")


def azzera_conferme() -> None:
    """Solo per i test."""
    _disarmi_in_attesa.clear()
