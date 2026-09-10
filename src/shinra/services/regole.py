"""Il motore: le regole ascoltano la casa e agiscono da sole.

`domain/regole.py` decide se una regola scatta; qui la si esegue, la si
programma e la si registra.

Tre cose che meritano di essere trovate leggendo, non deducendo:

**Ogni scatto passa dal registro.** Non e' contabilita': e' l'unica risposta
possibile alla domanda «perche' si e' accesa la luce?». Una casa che agisce da
sola e non sa dire perche' e' una casa che si spegne.

**Il rifiuto e' registrato quanto l'esecuzione.** Una regola che non scatta
mai e una regola rotta si somigliano troppo, e senza il motivo scritto da
qualche parte l'unico modo di distinguerle e' rileggere il codice.

**Un ciclo si ferma e si racconta.** Due regole che si innescano a vicenda
vengono fermate — quello e' il minimo — e generano un avviso con dentro la
catena: senza i nomi in ordine, «una regola ha creato un ciclo» manda a
rileggerle tutte.

Riferimento: issue #27.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from shinra.domain import grafo as grafo_dominio
from shinra.domain import regole as dominio
from shinra.domain.eventi import (
    CASA_ABITATA,
    CASA_VUOTA,
    HA_STATO_CAMBIATO,
    PERSONA_RIENTRATA,
    PERSONA_USCITA,
    Evento,
    bus,
)

logger = logging.getLogger("Shinra.Regole")

PREFISSO_JOB = "regola_"

# Da dove viene una regola. Vuoto per quelle scritte a mano.
ORIGINE_GRAFO = "grafo:"

# Gli eventi del bus su cui una regola puo' essere innescata. Non tutti:
# `notifica.avviso` e' cio' che una regola produce, e ascoltarlo sarebbe il
# modo piu' breve per costruire un ciclo senza volerlo.
EVENTI_ASCOLTATI = (
    HA_STATO_CAMBIATO,
    CASA_ABITATA,
    CASA_VUOTA,
    PERSONA_RIENTRATA,
    PERSONA_USCITA,
)


def _identificativo_generato(modalita_id: str, nodo_id: str) -> str:
    """L'identificativo della regola nata da **questo** nodo di questa routine.

    Deterministico di proposito: risalvare il disegno deve riscrivere la
    stessa regola, non aggiungerne una seconda identica. Un identificativo
    casuale renderebbe ogni salvataggio un duplicato, e in una settimana la
    stessa routine avrebbe dieci regole che fanno tutte la stessa cosa.

    E' un'impronta e non i due nomi concatenati perche' la colonna e' lunga
    trentadue caratteri e un identificativo di nodo puo' essere lungo quanto
    vuole: troncare due nomi vuol dire farli collidere.
    """
    impronta = hashlib.sha256(f"{modalita_id}\n{nodo_id}".encode()).hexdigest()
    return f"reg_g{impronta[:16]}"


def _dalla_riga(riga: Mapping[str, Any]) -> dominio.Regola:
    return dominio.Regola(
        identificativo=str(riga.get("id")),
        nome=str(riga.get("nome") or ""),
        trigger=dict(riga.get("trigger") or {}),
        condizioni=list(riga.get("condizioni") or []),
        azioni=list(riga.get("azioni") or []),
        attiva=bool(riga.get("attiva", True)),
    )


class MotoreRegole:
    def __init__(self) -> None:
        self._annulla: list[Any] = []
        self.attivo = False

    # ------------------------------------------------------------ ciclo

    def avvia(self) -> bool:
        if self._annulla:
            return False
        for tipo in EVENTI_ASCOLTATI:
            self._annulla.append(bus.sottoscrivi(tipo, self._su_evento))
        self.riprogramma_tutte()
        self.attivo = True
        logger.info("Motore regole in ascolto.")
        return True

    def ferma(self) -> None:
        for annulla in self._annulla:
            annulla()
        self._annulla = []
        self.attivo = False

    # -------------------------------------------------- gli inneschi

    async def _su_evento(self, evento: Evento) -> None:
        for regola in self.regole_attive():
            if dominio.scatta_su_evento(regola, evento.tipo, evento.dati or {}):
                await self.esegui(regola, motivo=f"evento {evento.tipo}")

    def regole_attive(self) -> list[dominio.Regola]:
        from shinra.infra.db import depositi

        return [_dalla_riga(r) for r in depositi.regole.attive()]

    # --------------------------------------------------- l'esecuzione

    async def esegui(
        self,
        regola: dominio.Regola,
        motivo: str = "",
        catena: Optional[Sequence[str]] = None,
    ) -> dict[str, Any]:
        """Valuta le condizioni ed esegue le azioni. Registra sempre."""
        from shinra.services import registro

        adesso = datetime.now()

        try:
            catena_nuova = dominio.verifica_catena(list(catena or []), regola.identificativo)
        except dominio.Ciclo as ciclo:
            await self._segnala_ciclo(ciclo)
            self._annota(regola, adesso, f"fermata: ciclo ({' -> '.join(ciclo.catena)})")
            return {"eseguita": False, "ciclo": ciclo.catena}

        stati, abitata = await self._come_sta_la_casa()
        impedimento = dominio.perche_no(regola, adesso, stati, abitata)

        if impedimento is not None:
            # Anche il rifiuto si registra: e' l'unico modo per distinguere
            # una regola che non deve scattare da una rotta.
            self._annota(regola, adesso, f"non eseguita: {impedimento}")
            registro.registra(
                "regola.saltata",
                esito="saltata",
                dettagli={
                    "regola": regola.identificativo,
                    "nome": regola.nome,
                    "motivo": impedimento,
                },
            )
            return {"eseguita": False, "motivo": impedimento}

        fatte = []
        for azione in regola.azioni or ():
            fatte.append(await self._azione(azione, regola, catena_nuova))

        riuscite = sum(1 for f in fatte if f.get("riuscita"))
        esito = f"{riuscite}/{len(fatte)} azioni" if fatte else "nessuna azione"
        self._annota(regola, adesso, esito)

        registro.registra(
            "regola.eseguita",
            esito="ok" if riuscite == len(fatte) else "parziale",
            dettagli={
                "regola": regola.identificativo,
                "nome": regola.nome,
                "motivo": motivo,
                "catena": catena_nuova,
                "azioni": fatte,
            },
        )
        logger.info("Regola «%s» eseguita: %s (%s).", regola.nome, esito, motivo)

        return {"eseguita": True, "azioni": fatte}

    async def _azione(
        self, azione: Mapping[str, Any], regola: dominio.Regola, catena: Sequence[str]
    ) -> dict[str, Any]:
        tipo = str(azione.get("tipo") or "")

        if tipo == dominio.AZIONE_MODALITA:
            from shinra.skills.ha_tools import activate_mode

            esito = await activate_mode(str(azione.get("modalita") or ""))
            return {"tipo": tipo, "riuscita": bool(esito.get("success")), "dettaglio": esito.get("message")}

        if tipo == dominio.AZIONE_DISPOSITIVO:
            from shinra.infra.homeassistant.client import client_home_assistant

            entita = str(azione.get("entity_id") or "")
            servizio = str(azione.get("servizio") or "turn_on")
            dominio_ha = entita.split(".")[0] if "." in entita else "homeassistant"
            dati = {"entity_id": entita, **(azione.get("dati") or {})}
            esito = await client_home_assistant().call_service(dominio_ha, servizio, dati)
            return {"tipo": tipo, "riuscita": bool(esito.get("success")), "entity_id": entita}

        if tipo == dominio.AZIONE_AVVISO:
            from shinra.domain import notifiche
            from shinra.services.notifiche import servizio_notifiche

            avviso = notifiche.Avviso(
                categoria=str(azione.get("categoria") or notifiche.PROMEMORIA),
                titolo=str(azione.get("titolo") or regola.nome),
                testo=str(azione.get("testo") or ""),
                priorita=str(azione.get("priorita") or notifiche.IMPORTANTE),
            )
            esito = await servizio_notifiche.avvisa(avviso)
            return {"tipo": tipo, "riuscita": esito["inviate"] > 0, "inviate": esito["inviate"]}

        return {"tipo": tipo or "sconosciuta", "riuscita": False}

    async def _segnala_ciclo(self, ciclo: dominio.Ciclo) -> None:
        """Fermare un ciclo e non dirlo lascia una casa che non fa quello che
        le e' stato chiesto, senza che nessuno sappia perche'."""
        from shinra.domain import notifiche
        from shinra.services import registro
        from shinra.services.notifiche import servizio_notifiche

        nomi = self._nomi(ciclo.catena)
        registro.registra("regola.ciclo", esito="fermata", dettagli={"catena": ciclo.catena, "nomi": nomi})
        logger.warning("Ciclo fra regole fermato: %s", " -> ".join(nomi))

        await servizio_notifiche.avvisa(
            notifiche.Avviso(
                categoria=notifiche.PROMEMORIA,
                titolo="Regole che si innescano a vicenda",
                testo=(
                    "Ho fermato una catena che si stava avvitando: "
                    + " → ".join(nomi)
                    + ". Finche' resta cosi', quelle regole non vengono eseguite."
                ),
                priorita=notifiche.IMPORTANTE,
                destinazione="/#regole",
            )
        )

    def _nomi(self, identificativi: Sequence[str]) -> list[str]:
        from shinra.infra.db import depositi

        per_id = {str(r["id"]): str(r.get("nome") or r["id"]) for r in depositi.regole.elenco()}
        return [per_id.get(i, i) for i in identificativi]

    def _annota(self, regola: dominio.Regola, quando: datetime, esito: str) -> None:
        from shinra.infra.db import depositi

        depositi.regole.aggiorna(
            regola.identificativo, {"ultimo_scatto": quando, "ultimo_esito": esito[:200]}
        )

    async def _come_sta_la_casa(self) -> tuple[dict[str, str], Optional[bool]]:
        """Lo stato del mondo, letto una volta per tutte le condizioni.

        `None` per l'abitata quando non si sa: non sapere chi c'e' non e'
        sapere che non c'e' nessuno, e il dominio si comporta di conseguenza.
        """
        from shinra.services.presenza import presenza

        stati: dict[str, str] = {}
        try:
            from shinra.infra.homeassistant.stati import cache_stati

            stati = {str(s.get("entity_id")): str(s.get("state", "")) for s in cache_stati.tutti()}
        except Exception:
            stati = {}

        stato_casa = presenza.stato
        return stati, (stato_casa.abitata if stato_casa.conosciuta else None)

    # ------------------------------------------------ le regole a orario

    def riprogramma_tutte(self) -> int:
        """Rimette nello scheduler i job delle regole a orario.

        Si rifa' da zero a ogni avvio e a ogni modifica: un job orfano di una
        regola cancellata continuerebbe a scattare, ed e' il difetto piu'
        difficile da diagnosticare — qualcosa si accende e non c'e' nessuna
        regola che lo spieghi.
        """
        from shinra.infra.db import depositi
        from shinra.infra.scheduler.motore import scheduler

        for riga in depositi.regole.elenco():
            scheduler.annulla(f"{PREFISSO_JOB}{riga['id']}")

        programmate = 0
        adesso = datetime.now()
        for regola in self.regole_attive():
            quando = dominio.prossimo_scatto(regola, adesso)
            if quando is None:
                continue
            if scheduler.programma_azione(
                f"{PREFISSO_JOB}{regola.identificativo}",
                _scatta_a_orario,
                [regola.identificativo],
                quando,
            ):
                programmate += 1

        if programmate:
            logger.info("Regole a orario programmate: %d.", programmate)
        return programmate

    # --------------------------------------------- le regole di un grafo

    def sincronizza_dal_grafo(self, modalita: Mapping[str, Any]) -> dict[str, Any]:
        """I nodi trigger di una routine diventano regole di questo motore.

        La scelta e' stata presa nella scheda #28 e vale la pena rileggerla
        qui: un grafo con un innesco all'alba **non** si porta dietro un
        secondo scheduler. Due motori che programmano la stessa casa si
        contendono lo stesso lavoro, e il secondo si scopre solo quando la
        luce si accende due volte.

        La sincronizzazione e' completa, non incrementale: si guarda cosa il
        disegno chiede adesso e si cancella tutto il resto. Aggiungere e
        basta lascerebbe dietro la regola di un nodo cancellato — qualcosa
        che si accende senza che niente lo spieghi, il difetto piu' difficile
        da diagnosticare in una casa che agisce da sola.

        Cosa **non** si tocca: se qualcuno ha disattivato la regola generata,
        resta disattivata. Risalvare il disegno per correggere un orario non
        deve riaccendere un'automazione che era stata messa a tacere.
        """
        from shinra.infra.db import depositi
        from shinra.infra.scheduler.motore import scheduler

        identificativo = str(modalita.get("id") or "")
        if not identificativo:
            return {"scritte": [], "rimosse": []}

        origine = f"{ORIGINE_GRAFO}{identificativo}"
        nome_routine = str(modalita.get("name") or identificativo)

        volute = {
            _identificativo_generato(identificativo, nodo_id): trigger
            for nodo_id, trigger in grafo_dominio.triggers_automatici(modalita.get("nodes") or [])
        }
        di_prima = {str(r["id"]): r for r in depositi.regole.per_origine(origine)}

        rimosse = []
        for id_regola in sorted(set(di_prima) - set(volute)):
            scheduler.annulla(f"{PREFISSO_JOB}{id_regola}")
            depositi.regole.cancella(id_regola)
            rimosse.append(id_regola)

        scritte = []
        for id_regola, trigger in volute.items():
            precedente = di_prima.get(id_regola)
            depositi.regole.salva(
                {
                    "id": id_regola,
                    "nome": f"{nome_routine}, {dominio.descrivi_trigger(trigger)}"[:160],
                    "attiva": bool(precedente.get("attiva", True)) if precedente else True,
                    "trigger": dict(trigger),
                    "condizioni": [],
                    "azioni": [{"tipo": dominio.AZIONE_MODALITA, "modalita": nome_routine}],
                    "origine": origine,
                    "ultimo_esito": str((precedente or {}).get("ultimo_esito") or ""),
                }
            )
            scritte.append(id_regola)

        if scritte or rimosse:
            logger.info(
                "Routine «%s»: %d regole dal grafo, %d rimosse.", nome_routine, len(scritte), len(rimosse)
            )
            self.riprogramma_tutte()

        return {"scritte": scritte, "rimosse": rimosse}

    def dimentica_il_grafo(self, modalita_id: str) -> list[str]:
        """Cancellata la routine, spariscono le regole che la facevano partire.

        Senza questo, cancellare una routine lascerebbe una regola che ogni
        mattina prova ad attivare una modalita' che non esiste piu': fallisce
        in silenzio, e l'unico segno e' una riga di registro che nessuno
        cerca perche' nessuno sa che c'e' qualcosa da cercare.
        """
        from shinra.infra.db import depositi
        from shinra.infra.scheduler.motore import scheduler

        rimosse = []
        for riga in depositi.regole.per_origine(f"{ORIGINE_GRAFO}{modalita_id}"):
            scheduler.annulla(f"{PREFISSO_JOB}{riga['id']}")
            depositi.regole.cancella(str(riga["id"]))
            rimosse.append(str(riga["id"]))
        if rimosse:
            self.riprogramma_tutte()
        return rimosse

    # ------------------------------------------------------- modifiche

    def crea(self, dati: Mapping[str, Any], autore: Optional[str] = None) -> dict[str, Any]:
        from shinra.infra.db import depositi

        voce = depositi.regole.aggiungi(
            {
                "id": f"reg_{uuid.uuid4().hex[:8]}",
                "nome": str(dati.get("nome") or "Regola"),
                "attiva": bool(dati.get("attiva", True)),
                "trigger": dict(dati.get("trigger") or {}),
                "condizioni": list(dati.get("condizioni") or []),
                "azioni": list(dati.get("azioni") or []),
                "autore": autore,
                "ultimo_esito": "",
            }
        )
        self.riprogramma_tutte()
        return voce

    def modifica(self, identificativo: str, dati: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        from shinra.infra.db import depositi

        voce = depositi.regole.aggiorna(identificativo, dict(dati))
        self.riprogramma_tutte()
        return voce

    def cancella(self, identificativo: str) -> bool:
        from shinra.infra.db import depositi
        from shinra.infra.scheduler.motore import scheduler

        scheduler.annulla(f"{PREFISSO_JOB}{identificativo}")
        esito = depositi.regole.cancella(identificativo)
        self.riprogramma_tutte()
        return esito

    def elenco(self) -> list[dict[str, Any]]:
        from shinra.infra.db import depositi

        return depositi.regole.elenco()

    def per_id(self, identificativo: str) -> Optional[dict[str, Any]]:
        from shinra.infra.db import depositi

        return depositi.regole.per_id(identificativo)

    async def esegui_per_id(self, identificativo: str, motivo: str = "") -> Optional[dict[str, Any]]:
        """Esegue una regola per identificativo, saltando il trigger.

        Sta qui e non nelle rotte perche' altrimenti le rotte dovrebbero
        leggere dall'archivio, e `api -> infra` e' il gruppo piu' numeroso
        del debito d'architettura: il ratchet ha bocciato la prima versione
        di questa rotta proprio per quello.
        """
        riga = self.per_id(identificativo)
        if riga is None:
            return None
        return await self.esegui(_dalla_riga(riga), motivo=motivo)


async def _scatta_a_orario(identificativo: str) -> None:
    """Il job dello scheduler. Riprogramma se stesso per la volta dopo."""
    from shinra.infra.db import depositi

    riga = depositi.regole.per_id(identificativo)
    if riga is None or not riga.get("attiva"):
        return

    await motore_regole.esegui(_dalla_riga(riga), motivo="orario")
    motore_regole.riprogramma_tutte()


motore_regole = MotoreRegole()
