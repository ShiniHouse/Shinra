"""Le rotte delle regole: crearle, provarle, spegnerle.

Una regola cambia cosa fa la casa da sola, quindi cambiarle richiede il
permesso di modificare le modalita': sono la stessa cosa vista da due lati —
una modalita' e' una sequenza che parte a comando, una regola e' una sequenza
che parte da sola, e la seconda e' piu' potente della prima.

`POST /prova` esegue una regola **saltando il trigger ma non le condizioni**.
E' voluto: serve a rispondere a «perche' non scatta?», e una prova che ignora
anche le condizioni risponderebbe sempre di si' e non direbbe niente.

Riferimento: issue #27.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shinra.api.sicurezza import richiedi_autenticazione, richiedi_permesso
from shinra.domain import regole as dominio
from shinra.services import permessi, regole_luoghi
from shinra.services.regole import EVENTI_ASCOLTATI, motore_regole
from shinra.services.user_manager import UserProfile
from shinra.skills.entita import EntitaSconosciuta
from shinra.skills.entita import verifica as verifica_entita
from shinra.skills.ha_tools import DOMINI_COMANDABILI

logger = logging.getLogger("Shinra.Regole")

router = APIRouter(
    prefix="/api/regole",
    tags=["Regole"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class RegolaIn(BaseModel):
    nome: str
    trigger: Dict[str, Any]
    condizioni: List[Dict[str, Any]] = Field(default_factory=list)
    azioni: List[Dict[str, Any]] = Field(default_factory=list)
    attiva: bool = True


class Modifica(BaseModel):
    nome: Optional[str] = None
    trigger: Optional[Dict[str, Any]] = None
    condizioni: Optional[List[Dict[str, Any]]] = None
    azioni: Optional[List[Dict[str, Any]]] = None
    attiva: Optional[bool] = None


async def _verifica_bersagli(azioni: List[Dict[str, Any]]) -> None:
    """Il dispositivo di un'azione deve esistere, e si salva col suo identificativo vero.

    Trovato provando in casa (#195): la scorciatoia salvava `Luce Acquario`, un nome e non un identificativo; la regola
    scattava, Home Assistant rispondeva 400, e l'elenco diceva «parziale» senza dire perche'. Un alias («luce cucina»)
    diventa il suo `entity_id`; un nome che non c'e' e' un rifiuto con il suggerimento piu' vicino.
    """
    for azione in azioni:
        if str(azione.get("tipo") or "") != dominio.AZIONE_DISPOSITIVO:
            continue
        try:
            azione["entity_id"] = await verifica_entita(
                str(azione.get("entity_id") or ""), DOMINI_COMANDABILI
            )
        except EntitaSconosciuta as errore:
            raise HTTPException(status_code=400, detail=str(errore)) from errore


def _valida_luogo(trigger: Dict[str, Any], azioni: Optional[List[Dict[str, Any]]] = None) -> None:
    """Un trigger su un luogo: un luogo registrato, arrivo o partenza, e una persona di Home Assistant.

    E **nessuna azione sensibile** (#192): una regola che apre una serratura, disarma l'allarme o alza il garage «arrivando»
    parte da sola, senza nessuno che la confermi, sulla parola di una posizione che puo' sbagliare di centinaia di metri.
    Quelle azioni non si legano a un luogo; chi le vuole le comanda quando e' arrivato.
    """
    from shinra.domain import sensibilita
    from shinra.services import luoghi

    if str(trigger.get("evento") or "") not in dominio.EVENTI_LUOGO:
        raise HTTPException(status_code=400, detail=f"Dimmi se è «{dominio.ARRIVO}» o «{dominio.PARTENZA}».")
    if not any(x["id"] == trigger.get("luogo_id") for x in luoghi.elenco()):
        raise HTTPException(status_code=400, detail="Il luogo non è fra quelli registrati.")
    if not str(trigger.get("entity_id") or "").startswith(("person.", "device_tracker.")):
        raise HTTPException(
            status_code=400,
            detail="Serve la persona (o il telefono) di Home Assistant che si sposta: `person.…` o `device_tracker.…`.",
        )
    for azione in azioni or []:
        if str(azione.get("tipo") or "") != dominio.AZIONE_DISPOSITIVO:
            continue
        if sensibilita.entita_sensibile(
            str(azione.get("entity_id") or ""), str(azione.get("servizio") or "turn_on")
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Una serratura, l'allarme, il garage o uno script non si comandano in automatico arrivando o partendo: "
                    "una posizione sbagliata di poche centinaia di metri aprirebbe la porta a nessuno. Toglila dalla regola."
                ),
            )


def _valida(regola: RegolaIn) -> None:
    """Rifiuta cio' che non potrebbe mai scattare.

    Una regola con un trigger sconosciuto viene salvata, non scatta mai, e
    sembra rotta senza dire perche'. Meglio rifiutarla adesso, quando c'e'
    ancora qualcuno che guarda.
    """
    tipo = str(regola.trigger.get("tipo") or "")
    if tipo not in dominio.TRIGGER:
        raise HTTPException(
            status_code=400,
            detail=f"Trigger «{tipo or 'assente'}» sconosciuto. Sono: {', '.join(dominio.TRIGGER)}.",
        )

    if tipo == dominio.EVENTO:
        evento = str(regola.trigger.get("evento") or "")
        if evento not in EVENTI_ASCOLTATI:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"L'evento «{evento or 'assente'}» non lo ascolta nessuno: la regola non scatterebbe mai. "
                    f"Gli eventi che si possono usare sono: {', '.join(EVENTI_ASCOLTATI)}."
                ),
            )

    if tipo == dominio.STATO:
        confronto = str(regola.trigger.get("confronto") or "")
        if confronto and confronto not in dominio.CONFRONTI:
            raise HTTPException(
                status_code=400,
                detail=f"Confronto «{confronto}» sconosciuto. Sono: {', '.join(dominio.CONFRONTI)}.",
            )
        if not regola.trigger.get("entity_id"):
            raise HTTPException(status_code=400, detail="Un trigger su stato ha bisogno di un'entita'.")

    if tipo == dominio.LUOGO:
        _valida_luogo(regola.trigger, regola.azioni)

    for condizione in regola.condizioni:
        if str(condizione.get("tipo") or "") not in dominio.CONDIZIONI:
            raise HTTPException(
                status_code=400,
                detail=f"Condizione «{condizione.get('tipo')}» sconosciuta.",
            )

    if not regola.azioni:
        raise HTTPException(
            status_code=400, detail="Una regola senza azioni non fa niente: aggiungine almeno una."
        )

    for azione in regola.azioni:
        tipo_azione = str(azione.get("tipo") or "")
        if tipo_azione not in dominio.AZIONI:
            raise HTTPException(status_code=400, detail=f"Azione «{azione.get('tipo')}» sconosciuta.")

        # Lo stesso metro di «una regola senza azioni non fa niente», un passo
        # piu' in la': un'azione che non dice **su cosa** agire non fa niente
        # lo stesso, ma in modo piu' silenzioso — la regola scatta, il
        # servizio viene chiamato su un'entita' vuota, e l'elenco mostra
        # «ultima volta: riuscita». Trovato provando a rompere la scorciatoia
        # della #126, che mandava volentieri un `entity_id` vuoto.
        if tipo_azione == dominio.AZIONE_DISPOSITIVO and not str(azione.get("entity_id") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Un'azione su un dispositivo ha bisogno di sapere quale: manca l'entita'.",
            )
        if tipo_azione == dominio.AZIONE_MODALITA and not str(azione.get("modalita") or "").strip():
            raise HTTPException(
                status_code=400, detail="Un'azione che avvia una routine ha bisogno del suo nome."
            )
        if tipo_azione == dominio.AZIONE_AVVISO and not str(azione.get("testo") or "").strip():
            raise HTTPException(status_code=400, detail="Un avviso senza testo non dice niente a nessuno.")


@router.get("")
async def elenco() -> Dict[str, Any]:
    """Le regole, con **quando scatteranno la prossima volta**.

    Il prossimo scatto non e' un abbellimento: e' la differenza fra una
    schermata che elenca regole e una che risponde alla domanda con cui ci si
    arriva, che e' sempre «e allora perche' non e' successo niente?». Una
    regola attiva e senza prossimo scatto e' esattamente il difetto che le
    regole del sole avevano da due versioni.
    """
    sole = motore_regole.sole_corrente()
    adesso = datetime.now()

    def _descritta(voce: Dict[str, Any]) -> Dict[str, Any]:
        regola = dominio.Regola(
            str(voce["id"]),
            str(voce.get("nome") or ""),
            dict(voce.get("trigger") or {}),
            list(voce.get("condizioni") or []),
            list(voce.get("azioni") or []),
            bool(voce.get("attiva", True)),
        )
        prossimo = (
            dominio.prossimo_scatto(regola, adesso, tramonto=sole.tramonto, alba=sole.alba)
            if regola.attiva
            else None
        )
        avviso = regole_luoghi.perche_non_scattera(regola.trigger or {}, regola.attiva)
        if str(regola.trigger.get("tipo") or "") == dominio.LUOGO:
            regola = dominio.Regola(
                regola.identificativo,
                regola.nome,
                {
                    **regola.trigger,
                    "luogo_nome": regole_luoghi.nome_del_luogo(regola.trigger.get("luogo_id")),
                },
                regola.condizioni,
                regola.azioni,
                regola.attiva,
            )
        return {
            **voce,
            "avviso": avviso,
            "descrizione": dominio.descrivi(regola),
            "prossimo": prossimo.isoformat() if prossimo else None,
            # Una regola su evento non ha un «prossimo» e sta benissimo:
            # aspetta che qualcosa succeda. Distinguerla da una che non
            # scattera' mai e' tutto il punto di questa schermata.
            "aspetta_un_evento": str((regola.trigger or {}).get("tipo") or "")
            in (dominio.EVENTO, dominio.STATO, dominio.LUOGO),
        }

    return {"regole": [_descritta(v) for v in motore_regole.elenco()]}


@router.post("", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def crea(
    dati: RegolaIn, profilo: Optional[UserProfile] = Depends(richiedi_autenticazione)
) -> Dict[str, Any]:
    """Crea una regola del motore (innesco, condizioni, azioni)."""
    _valida(dati)
    await _verifica_bersagli(dati.azioni)
    voce = motore_regole.crea(dati.model_dump(), autore=profilo.id if profilo else None)
    return {"success": True, "regola": voce}


@router.patch("/{identificativo}", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def modifica(identificativo: str, dati: Modifica) -> Dict[str, Any]:
    """Modifica una regola esistente."""
    if dati.azioni:
        await _verifica_bersagli(dati.azioni)
    cambiamenti = {k: v for k, v in dati.model_dump().items() if v is not None}
    if not cambiamenti:
        raise HTTPException(status_code=400, detail="Non c'e' niente da cambiare.")

    # La regola com'e' dopo la modifica: un trigger su un luogo (anche gia' presente) con un'azione sensibile non si accetta,
    # qualunque dei due pezzi si cambi.
    attuale = motore_regole.per_id(identificativo)
    if attuale is not None:
        trigger = cambiamenti.get("trigger", attuale.get("trigger") or {})
        if str(trigger.get("tipo") or "") == dominio.LUOGO:
            _valida_luogo(trigger, cambiamenti.get("azioni", attuale.get("azioni") or []))

    voce = motore_regole.modifica(identificativo, cambiamenti)
    if voce is None:
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    return {"success": True, "regola": voce}


@router.delete("/{identificativo}", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def cancella(identificativo: str) -> Dict[str, Any]:
    """Cancella una regola."""
    if not motore_regole.cancella(identificativo):
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    return {"success": True}


@router.post("/{identificativo}/prova", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def prova(identificativo: str) -> Dict[str, Any]:
    """Esegue la regola saltando il trigger, **ma non le condizioni**.

    Serve a rispondere a «perche' non scatta?»: se le condizioni non sono
    soddisfatte la risposta lo dice, ed e' quasi sempre la risposta giusta.
    """
    esito = await motore_regole.esegui_per_id(identificativo, motivo="prova manuale")
    if esito is None:
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    return {"success": esito.get("eseguita", False), **esito}
