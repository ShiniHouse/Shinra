"""Consumi, costi e fasce: cosa la casa sa dire sull'energia.

`domain/fasce.py` sa in che fascia siamo; `domain/energia.py` sa fare i
conti. Qui si leggono i sensori di Home Assistant, si interroga lo storico e
si risponde a una persona.

La regola che attraversa tutto il file: **quando i dati non ci sono, si dice
che non ci sono.** «Zero kilowattora» e «non lo so» sono risposte diverse, e
la prima detta al posto della seconda e' il modo piu' rapido per far perdere
fiducia a un conto in bolletta. Vale per i sensori assenti, per lo storico
troppo corto, e per la tariffa non configurata — che non blocca la risposta
ma la fa dichiarare stimata.

Riferimento: issue #24.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Sequence

from shinra.config.settings import settings
from shinra.domain import energia as dominio
from shinra.domain import fasce

logger = logging.getLogger("Shinra.Energia")

# Come Home Assistant marca un sensore che conta energia. `total` e
# `total_increasing` sono contatori cumulativi; `measurement` e' una potenza
# istantanea, che e' un'altra cosa e non va sommata.
CLASSI_ENERGIA = frozenset({"energy"})
CLASSI_POTENZA = frozenset({"power"})
CONTATORI = frozenset({"total", "total_increasing"})


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


def tariffa_configurata() -> dominio.Tariffa:
    """La tariffa di casa, o una stima dichiarata tale.

    Le opzioni si leggono per esteso (`settings.energia.prezzo_punta` e non
    un alias piu' corto) perche' il guardiano della issue #26 cerca proprio
    quelle stringhe nel codice: un'opzione che nessuna riga nomina e'
    un'opzione che finisce nel pannello e non fa niente.
    """
    tipo = (settings.energia.tipo or "").strip().lower()

    if tipo == dominio.BIORARIA and settings.energia.prezzo_punta > 0:
        return dominio.tariffa_bioraria(
            settings.energia.prezzo_punta,
            settings.energia.prezzo_fuori_punta or settings.energia.prezzo_punta,
        )

    if tipo == dominio.TRIORARIA and settings.energia.prezzo_punta > 0:
        return dominio.tariffa_trioraria(
            settings.energia.prezzo_punta,
            settings.energia.prezzo_f2 or settings.energia.prezzo_punta,
            settings.energia.prezzo_f3 or settings.energia.prezzo_punta,
        )

    if settings.energia.prezzo_kwh > 0:
        return dominio.tariffa_monoraria(settings.energia.prezzo_kwh)

    return dominio.tariffa_di_ripiego()


def _stima(tariffa: dominio.Tariffa) -> str:
    if not tariffa.stimata:
        return ""
    return (
        f" Il costo e' una stima a {dominio.in_euro(dominio.PREZZO_DI_RIPIEGO)} al "
        "kilowattora: configura la tua tariffa per avere il conto vero."
    )


# ------------------------------------------------------ i sensori della casa


def sensori_energia(stati: Sequence[dict[str, Any]]) -> list[str]:
    """I contatori di energia, non le potenze istantanee.

    Un sensore `power` dice quanti watt sta assorbendo adesso; un sensore
    `energy` dice quanti kilowattora ha totalizzato. Sommare i primi darebbe
    un numero senza significato.
    """
    trovati = []
    for stato in stati:
        attributi = stato.get("attributes") or {}
        if str(attributi.get("device_class", "")).lower() not in CLASSI_ENERGIA:
            continue
        classe = str(attributi.get("state_class", "")).lower()
        if classe and classe not in CONTATORI:
            continue
        trovati.append(str(stato.get("entity_id", "")))
    return [e for e in trovati if e]


def sensori_potenza(stati: Sequence[dict[str, Any]]) -> list[str]:
    return [
        str(s.get("entity_id", ""))
        for s in stati
        if str((s.get("attributes") or {}).get("device_class", "")).lower() in CLASSI_POTENZA
    ]


def _valore(stato: dict[str, Any]) -> Optional[float]:
    """Il numero che segna il sensore, o `None` se non ne segna uno.

    `unavailable` e `unknown` finiscono qui, ed e' il motivo per cui questa
    funzione torna `None` invece di zero: uno zero in mezzo a un contatore
    cumulativo diventerebbe un azzeramento.
    """
    grezzo = stato.get("state")
    if grezzo is None:
        return None
    try:
        return float(grezzo)
    except (TypeError, ValueError):
        return None


async def _stati() -> list[dict[str, Any]]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return list(await client_home_assistant().stati_correnti())


# ------------------------------------------------------------------ i tool


async def fascia_corrente() -> Dict[str, Any]:
    """In che fascia siamo adesso, e quando cambia."""
    adesso = datetime.now(fasce.FUSO)
    corrente = fasce.fascia(adesso)
    cambio = fasce.prossimo_cambio(adesso)
    dopo = fasce.fascia(cambio)

    quando = cambio.strftime("%H:%M")
    if cambio.date() != adesso.date():
        quando = (
            f"{quando} di domani"
            if (cambio.date() - adesso.date()).days == 1
            else cambio.strftime("%d/%m alle %H:%M")
        )

    return _riuscito(
        f"{fasce.descrivi(adesso)} Si passa a {dopo} alle {quando}.",
        fascia=corrente,
        prossima=dopo,
        cambio=cambio.isoformat(),
    )


async def consumo_energia(periodo: str = "oggi", entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Quanto e' stato consumato, e quanto e' costato."""
    from shinra.infra.db import depositi

    da, a, detto = _intervallo(periodo)

    righe = depositi.letture_energia.fra(da, a, entity_id)
    if not righe:
        return _senza_storico(entity_id)

    totali = dict.fromkeys(fasce.FASCE, 0.0)
    for riga in righe:
        fascia = str(riga.get("fascia") or "") or fasce.F3
        totali[fascia] = totali.get(fascia, 0.0) + float(riga.get("consumo") or 0.0)

    consumo = dominio.Consumo({f: round(v, 3) for f, v in totali.items()})
    tariffa = tariffa_configurata()
    costo = consumo.costo(tariffa)

    if consumo.totale <= 0:
        return _riuscito(
            f"Ho letture per {detto} ma nessun consumo registrato: i contatori non " "sono cambiati.",
            kwh=0.0,
            costo=0.0,
        )

    dominante = consumo.dominante()
    dettaglio = ", ".join(
        f"{f} {consumo.per_fascia[f]:.2f}" for f in fasce.FASCE if consumo.per_fascia[f] > 0
    )

    return _riuscito(
        f"{detto.capitalize()}: {consumo.totale:.2f} kilowattora, circa "
        f"{dominio.in_euro(costo)} ({dettaglio} kWh). La fascia piu' cara di consumo "
        f"e' stata {dominante}.{_stima(tariffa)}",
        kwh=consumo.totale,
        costo=costo,
        per_fascia=dict(consumo.per_fascia),
        stimato=tariffa.stimata,
    )


async def costo_dispositivo(entity_id: str) -> Dict[str, Any]:
    """Quanto costa tenere acceso questo, un'ora, adesso."""
    from shinra.skills.entita import nome_di, risolvi

    stati = await _stati()
    entita = risolvi(entity_id)

    misura = next((s for s in stati if s.get("entity_id") == entita), None)
    if misura is None:
        return _fallito(f"Non conosco «{entity_id}».")

    watt = _valore(misura)
    attributi = misura.get("attributes") or {}
    if watt is None or str(attributi.get("device_class", "")).lower() not in CLASSI_POTENZA:
        candidati = sensori_potenza(stati)
        if not candidati:
            return _fallito(
                "Non ho un sensore di potenza per quel dispositivo, quindi non "
                "posso sapere quanto assorbe. Servirebbe una presa che misura."
            )
        return _fallito(
            f"«{nome_di(entita, stati)}» non misura la potenza. Sensori che la "
            f"misurano: {', '.join(candidati[:5])}."
        )

    adesso = datetime.now(fasce.FUSO)
    tariffa = tariffa_configurata()
    orario = dominio.costo_orario(watt, tariffa, adesso)
    corrente = fasce.fascia(adesso)

    return _riuscito(
        f"{nome_di(entita, stati)} assorbe {watt:.0f} watt: in {corrente} costa "
        f"circa {dominio.in_euro(orario)} l'ora, {dominio.in_euro(round(orario * 24, 2))} "
        f"al giorno se resta acceso.{_stima(tariffa)}",
        watt=watt,
        costo_orario=orario,
        fascia=corrente,
        stimato=tariffa.stimata,
    )


# --------------------------------------------------------------- di supporto


def _intervallo(periodo: str) -> tuple[datetime, datetime, str]:
    """Da «oggi», «ieri», «settimana», «mese» a due istanti.

    **Ogni finestra si chiude su una mezzanotte, non su «adesso».** Prima
    l'estremo superiore era l'istante della domanda, e `letture_energia.fra`
    confronta con il minore stretto: una lettura registrata nello stesso tick
    di orologio della domanda aveva `momento == a` e spariva, in silenzio.
    Non era un caso di scuola — lo scheduler campiona i contatori e poi
    qualcuno chiede «quanto ho consumato oggi»: se le due cose capitano
    vicine, l'ultima lettura non entrava nel conto e il numero usciva piu'
    basso del vero senza che niente lo segnalasse.

    Si vedeva a intermittenza solo dove l'orologio e' grosso — su Windows la
    granularita' e' di circa quindici millisecondi, su Linux di un
    microsecondo — quindi la suite era verde in CI e rossa a caso altrove.
    «Ieri» non ne soffriva perche' usava gia' due mezzanotte: adesso lo fanno
    tutti. Riferimento: issue #101.
    """
    adesso = datetime.now(timezone.utc)
    locale = adesso.astimezone(fasce.FUSO)
    mezzanotte = locale.replace(hour=0, minute=0, second=0, microsecond=0)
    # La mezzanotte che viene, non fra ventiquattr'ore: l'aritmetica su un
    # datetime con fuso sposta l'ora di parete e `zoneinfo` ricalcola lo
    # scarto da UTC alla conversione, quindi il cambio dell'ora non sposta il
    # confine della giornata.
    domani = mezzanotte + timedelta(days=1)

    scelta = (periodo or "oggi").strip().lower()

    if scelta in ("ieri",):
        return (
            (mezzanotte - timedelta(days=1)).astimezone(timezone.utc),
            mezzanotte.astimezone(timezone.utc),
            "ieri",
        )
    if scelta in ("settimana", "questa settimana", "ultimi 7 giorni"):
        return (
            (mezzanotte - timedelta(days=7)).astimezone(timezone.utc),
            domani.astimezone(timezone.utc),
            "negli ultimi sette giorni",
        )
    if scelta in ("mese", "questo mese", "ultimi 30 giorni"):
        return (
            (mezzanotte - timedelta(days=30)).astimezone(timezone.utc),
            domani.astimezone(timezone.utc),
            "negli ultimi trenta giorni",
        )

    return mezzanotte.astimezone(timezone.utc), domani.astimezone(timezone.utc), "oggi"


def _senza_storico(entity_id: Optional[str]) -> Dict[str, Any]:
    """Il criterio di accettazione della scheda: senza sensori lo si dice,
    invece di inventare un numero."""
    from shinra.infra.db import depositi

    note = depositi.letture_energia.entita_note()

    if entity_id and note:
        return _fallito(
            f"Non ho letture di «{entity_id}» per quel periodo. " f"Sto registrando: {', '.join(note[:5])}."
        )
    if not note:
        return _fallito(
            "Non ho ancora letture dei contatori. O Home Assistant non espone "
            "sensori di energia, o il monitoraggio e' partito da poco: il "
            "primo consumo si sa dopo due letture, cioe' dopo un'ora."
        )
    return _fallito("Non ho letture per quel periodo.")
