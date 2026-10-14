"""I riassunti delle conversazioni: salvarli, rileggerli, farli scadere, dimenticarli (#255, ADR 0010).

Si conserva il **riassunto**, non il testo grezzo; per profilo; con una scadenza (30 giorni); mai per gli ospiti; per un
minore (`child`, `teen`) solo l'**argomento** — le azioni eseguite — e non il testo di cio' che ha scritto. Non passa da un
servizio esterno e non esce in un salvataggio. Chi dice «dimentica» li cancella subito.

Il riassunto e' scritto dal codice dai fatti verificati (`domain/riassunto.py`): le risposte libere del modello non
entrano. Se il modello locale e' acceso potra' renderlo piu' leggibile (#256), ma il testo di base e' sempre questo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from shinra.domain import riassunto as dominio
from shinra.infra.db.riassunti import riassunti as deposito
from shinra.infra.lingue import schemi

logger = logging.getLogger("Shinra.Riassunti")

GIORNI_DI_VALIDITA = 30
RUOLI_SENZA_MEMORIA = ("guest",)
RUOLI_SOLO_ARGOMENTO = ("child", "teen")
# Quanti riassunti recenti si mettono davanti ai turni grezzi, e quanto testo al massimo: il budget del contesto e' stretto.
RIASSUNTI_NEL_PROMPT = 2
CARATTERI_NEL_PROMPT = 480


def _ora(adesso: Optional[datetime]) -> datetime:
    # Le date del database sono UTC senza fuso: si confrontano cosi'.
    return (adesso or datetime.now(timezone.utc)).replace(tzinfo=None)


def e_conservabile(ruolo: Optional[str], profilo_id: str) -> bool:
    """Gli ospiti non hanno memoria persistente (ADR 0010), e senza un profilo non c'e' di chi conservare."""
    return bool(profilo_id) and profilo_id != "guest" and (ruolo or "") not in RUOLI_SENZA_MEMORIA


def come_testo(riassunto: dominio.Riassunto, lingua: str = "", solo_argomento: bool = False) -> str:
    """Il riassunto detto in parole, nella lingua del profilo."""
    s = schemi(lingua)
    parti = []
    if riassunto.richieste and not solo_argomento:
        parti.append(s.dice("riassunto_richieste", voci="; ".join(f"«{r}»" for r in riassunto.richieste)))
    if riassunto.azioni:
        fallita = s.dice("riassunto_non_riuscita")
        voci = ", ".join(a.nome if a.riuscita else f"{a.nome} ({fallita})" for a in riassunto.azioni)
        parti.append(s.dice("riassunto_azioni", voci=voci))
    return " ".join(parti)


def salva(
    profilo_id: str,
    ruolo: Optional[str],
    messaggi: Sequence[Mapping[str, Any]],
    lingua: str = "",
    adesso: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Riassume questi messaggi che escono dalla finestra e li conserva. `None` se non c'e' nulla da tenere o non si puo'."""
    if not e_conservabile(ruolo, profilo_id):
        return None
    riassunto = dominio.riassumi(messaggi, schemi(lingua).sospetto)
    solo_argomento = (ruolo or "") in RUOLI_SOLO_ARGOMENTO
    testo = come_testo(riassunto, lingua, solo_argomento)
    if not testo:
        return None
    ora = _ora(adesso)
    try:
        return deposito.aggiungi(
            profilo_id,
            testo,
            riassunto.turni,
            creato_il=ora,
            scade_il=ora + timedelta(days=GIORNI_DI_VALIDITA),
            struttura={
                "richieste": [] if solo_argomento else list(riassunto.richieste),
                "azioni": [{"nome": a.nome, "riuscita": a.riuscita} for a in riassunto.azioni],
                "lingua": lingua,
            },
        )
    except Exception:
        logger.warning("Riassunto non conservato", exc_info=True)
        return None


def per_il_prompt(profilo_id: str, ruolo: Optional[str] = None, adesso: Optional[datetime] = None) -> str:
    """I riassunti recenti **di questo profilo**, per mettere davanti ai turni grezzi. Mai quelli di un altro."""
    if not e_conservabile(ruolo, profilo_id):
        return ""
    recenti = deposito.del_profilo(profilo_id, ancora_validi_a=_ora(adesso), massimo=RIASSUNTI_NEL_PROMPT)
    testo = " ".join(r["testo"] for r in reversed(recenti))
    return testo if len(testo) <= CARATTERI_NEL_PROMPT else testo[: CARATTERI_NEL_PROMPT - 1].rstrip() + "…"


def dimentica(profilo_id: str) -> int:
    """Cancella subito tutti i riassunti di un profilo."""
    return deposito.dimentica_profilo(profilo_id) if profilo_id else 0


def purga_scaduti(adesso: Optional[datetime] = None) -> int:
    """Toglie i riassunti scaduti. Gira ogni giorno."""
    return deposito.purga_scaduti(_ora(adesso))


def alla_uscita(chiave: str, messaggi: Sequence[Mapping[str, Any]]) -> None:
    """Chiamata dal gestore delle conversazioni quando dei messaggi escono dalla finestra: li riassume e li conserva.

    Solo per un profilo che esiste: di un ospite non registrato non si conserva niente.
    """
    from shinra.services.user_manager import user_manager

    profilo = user_manager.get_user_by_id(chiave)
    if profilo is None:
        return
    salva(profilo.id, profilo.role, messaggi, getattr(profilo, "lingua", "") or "")


async def _purga() -> None:
    quanti = purga_scaduti()
    if quanti:
        logger.info("Riassunti scaduti tolti: %d", quanti)


def avvia() -> bool:
    """Mette il servizio in ascolto delle conversazioni e programma la pulizia giornaliera dei riassunti scaduti."""
    from shinra.infra.scheduler.motore import scheduler
    from shinra.services.memory import gestore_memorie

    gestore_memorie.su_uscita = alla_uscita
    # Di notte, quando la casa dorme: la riscrittura costa secondi su una CPU senza scheda grafica.
    scheduler.programma_giornaliero("riassunti:rifinitura", _rifinitura_notturna, ora=3, minuto=40)
    return scheduler.programma_periodico("riassunti:purga", _purga, ore=24)


def ferma() -> None:
    from shinra.infra.scheduler.motore import scheduler
    from shinra.services.memory import gestore_memorie

    gestore_memorie.su_uscita = None
    scheduler.annulla("riassunti:purga")
    scheduler.annulla("riassunti:rifinitura")


# ------------------------------------------------- la riscrittura notturna (#256)

GIORNI_DA_RIFINIRE = 3
TETTO_RIFINITURA_SECONDI = 15 * 60


async def rifinisci_recenti(
    chat: Any = None, adesso: Optional[datetime] = None, massimo: int = 20
) -> dict[str, int]:
    """Chiede al modello locale di rendere piu' leggibili i riassunti recenti, **fuori dal percorso di ogni risposta**.

    Il modello riceve solo il testo scritto dal codice e deve restituirlo piu' leggibile senza aggiungere nulla: una
    riscrittura sostituisce l'originale solo se `controlla_riscrittura` la accetta, altrimenti resta il testo del codice.
    Se il modello non risponde si smette subito (si riprova la notte dopo): mai un errore a nessuno.
    """
    from shinra.infra.llm.ollama import OllamaClient

    cliente = chat or OllamaClient()
    modello = str(getattr(cliente, "model", "") or "")
    conta = {"visti": 0, "riscritti": 0, "rifiutati": 0, "saltati": 0}
    dopo = _ora(adesso) - timedelta(days=GIORNI_DA_RIFINIRE)
    for r in deposito.da_rifinire(dopo, massimo):
        conta["visti"] += 1
        struttura = r.get("struttura") or {}
        lingua = str(struttura.get("lingua") or "")
        s = schemi(lingua)
        try:
            esito = await cliente.chat(
                messages=[{"role": "user", "content": s.prompt_di("riassunto_riscrivi", testo=r["testo"])}],
                temperature=0.1,
            )
        except Exception:
            logger.warning("Riscrittura di un riassunto non riuscita", exc_info=True)
            conta["saltati"] += 1
            break
        if not esito.get("success"):
            conta["saltati"] += 1
            break  # il modello e' spento o lento: si riprova la notte dopo
        riscritto = str(esito.get("content") or "")
        verdetto = dominio.controlla_riscrittura(struttura, r["testo"], riscritto, s.sospetto)
        if verdetto.accettata and deposito.riscrivi(r["id"], " ".join(riscritto.split()), modello):
            conta["riscritti"] += 1
        else:
            conta["rifiutati"] += 1
    if conta["visti"]:
        logger.info("Riassunti rifiniti: %s", conta)
    return conta


async def _rifinitura_notturna() -> None:
    from shinra.services.compito_notturno import compito_notturno

    await compito_notturno.esegui("riassunti_rifiniti", rifinisci_recenti, TETTO_RIFINITURA_SECONDI)
