"""I depositi: l'unico posto da cui si leggono e si scrivono i dati di casa.

Ogni deposito restituisce e accetta dizionari con le stesse chiavi di prima
(`id`, `text`, `enabled`, ...). E' voluto: sopra ci sono le rotte HTTP e
l'interfaccia web, che quelle chiavi le usano gia'. La migrazione cambia
**dove** stanno i dati, non che aspetto hanno.

La differenza che conta e' `aggiungi`/`aggiorna`/`cancella`: toccano una riga
sola, dentro una transazione. Con i file JSON ogni modifica riscriveva
l'intero elenco, quindi due salvataggi in parallelo — la dashboard e l'Echo —
si sovrascrivevano a vicenda e uno dei due spariva senza lasciare traccia.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Type

from sqlalchemy import delete, select

from shinra.infra.db.modelli import (
    Alias,
    Base,
    EventoCalendario,
    Fatto,
    Fonte,
    LetturaEnergia,
    Lista,
    Modalita,
    Promemoria,
    Ruolo,
    ScadenzaManutenzione,
    Timer,
    Utente,
    VoceLista,
)
from shinra.infra.db.motore import sessione

logger = logging.getLogger("Shinra.Archivio")


def _come_dizionario(riga: Base, campi: Sequence[str]) -> dict[str, Any]:
    return {c: getattr(riga, c) for c in campi}


class Deposito:
    """Le operazioni comuni a tutte le tabelle con identificativo testuale."""

    modello: Type[Base]
    campi: tuple[str, ...]
    ordine: Optional[str] = None

    def elenco(self) -> list[dict[str, Any]]:
        with sessione() as s:
            query = select(self.modello)
            if self.ordine:
                query = query.order_by(getattr(self.modello, self.ordine))
            return [_come_dizionario(r, self.campi) for r in s.scalars(query).all()]

    def per_id(self, identificativo: str) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.get(self.modello, identificativo)
            return _come_dizionario(riga, self.campi) if riga else None

    def aggiungi(self, dati: dict[str, Any]) -> dict[str, Any]:
        """Inserisce una riga sola. Non rilegge e non riscrive le altre."""
        with sessione() as s:
            riga = self.modello(**{c: dati[c] for c in self.campi if c in dati})
            s.add(riga)
            s.flush()
            return _come_dizionario(riga, self.campi)

    def aggiorna(self, identificativo: str, dati: dict[str, Any]) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.get(self.modello, identificativo)
            if riga is None:
                return None
            for c in self.campi:
                if c != "id" and c in dati:
                    setattr(riga, c, dati[c])
            s.flush()
            return _come_dizionario(riga, self.campi)

    def salva(self, dati: dict[str, Any]) -> dict[str, Any]:
        """Inserisce o aggiorna, secondo che l'identificativo esista gia'."""
        esistente = self.aggiorna(dati["id"], dati)
        return esistente if esistente is not None else self.aggiungi(dati)

    def cancella(self, identificativo: str) -> bool:
        with sessione() as s:
            riga = s.get(self.modello, identificativo)
            if riga is None:
                return False
            s.delete(riga)
            return True

    def sostituisci_tutto(self, elementi: list[dict[str, Any]]) -> int:
        """Rimpiazza l'intero contenuto, in una transazione sola.

        E' la forma che serve alle rotte scritte per i file JSON, dove
        «salvare» significava riscrivere l'elenco. Qui almeno o riesce tutto
        o non cambia niente: non esiste piu' il caso del file troncato a
        meta'. Resta comunque preferibile `salva`/`cancella`, che non
        sovrascrivono cio' che ha appena fatto qualcun altro.
        """
        with sessione() as s:
            s.execute(delete(self.modello))
            for dati in elementi:
                s.add(self.modello(**{c: dati[c] for c in self.campi if c in dati}))
            return len(elementi)

    def conta(self) -> int:
        with sessione() as s:
            return len(s.scalars(select(self.modello.id)).all())  # type: ignore[attr-defined]


class DepositoUtenti(Deposito):
    modello = Utente
    campi = (
        "id",
        "name",
        "role",
        "age_group",
        "gender",
        "avatar_type",
        "pin",
        "preferred_news_categories",
        "restricted_topics",
        "notes",
    )
    ordine = "name"

    def imposta_pin(self, identificativo: str, pin_cifrato: Optional[str]) -> bool:
        """Scrive solo la colonna del PIN.

        Con i file JSON questa operazione riscriveva l'intera anagrafica: se
        qualcuno stava salvando un profilo nello stesso momento, una delle
        due modifiche spariva. Cambiare il PIN e perderlo subito dopo e' il
        modo piu' rapido per restare chiusi fuori di casa.
        """
        with sessione() as s:
            riga = s.get(Utente, identificativo)
            if riga is None:
                return False
            riga.pin = pin_cifrato
            return True


class DepositoRuoli(Deposito):
    modello = Ruolo
    campi = ("id", "nome", "descrizione", "permessi", "predefinito")
    ordine = "nome"


class DepositoFatti(Deposito):
    modello = Fatto
    campi = ("id", "text", "category", "enabled")

    def aggiungi_fatto(self, testo: str, categoria: str = "generale", attivo: bool = True) -> dict[str, Any]:
        pulito = (testo or "").strip()
        if not pulito:
            raise ValueError("Il testo del fatto non puo' essere vuoto.")

        # Durante un'intervista capita di ripetersi, e ogni fatto finisce nel
        # prompt di ogni risposta: i doppioni si pagano a ogni domanda.
        with sessione() as s:
            for riga in s.scalars(select(Fatto)).all():
                if (riga.text or "").strip().casefold() == pulito.casefold():
                    return _come_dizionario(riga, self.campi)

        return self.aggiungi(
            {
                "id": f"k_{uuid.uuid4().hex[:8]}",
                "text": pulito,
                "category": (categoria or "generale").strip() or "generale",
                "enabled": bool(attivo),
            }
        )


class DepositoAlias(Deposito):
    modello = Alias
    campi = ("id", "alias", "entity_id", "room", "domain")
    ordine = "alias"


class DepositoModalita(Deposito):
    modello = Modalita
    campi = ("id", "name", "icon", "trigger_phrases", "description", "enabled", "actions")
    ordine = "name"


class DepositoFonti(Deposito):
    modello = Fonte
    campi = ("id", "name", "category", "url", "enabled")
    ordine = "name"


class DepositoTimer(Deposito):
    modello = Timer
    campi = (
        "id",
        "label",
        "duration_seconds",
        "started_at",
        "expires_at",
        "user_id",
        "completed",
        "completed_at",
    )
    ordine = "expires_at"

    def attivi(self) -> list[dict[str, Any]]:
        with sessione() as s:
            query = select(Timer).where(Timer.completed.is_(False)).order_by(Timer.expires_at)
            return [_come_dizionario(r, self.campi) for r in s.scalars(query).all()]

    def segna_completato(self, identificativo: str) -> bool:
        with sessione() as s:
            riga = s.get(Timer, identificativo)
            if riga is None:
                return False
            riga.completed = True
            riga.completed_at = datetime.now().isoformat()
            return True

    def pulisci_completati(self, conserva_ore: int = 24) -> int:
        limite = time.time() - conserva_ore * 3600
        with sessione() as s:
            vecchi = s.scalars(
                select(Timer).where(Timer.completed.is_(True), Timer.expires_at <= limite)
            ).all()
            for riga in vecchi:
                s.delete(riga)
            return len(vecchi)


class DepositoPromemoria(Deposito):
    modello = Promemoria
    campi = ("id", "text", "remind_at", "user_id", "completed", "created_at", "completed_at")
    ordine = "remind_at"

    def attivi(self) -> list[dict[str, Any]]:
        with sessione() as s:
            query = select(Promemoria).where(Promemoria.completed.is_(False)).order_by(Promemoria.remind_at)
            return [_come_dizionario(r, self.campi) for r in s.scalars(query).all()]

    def segna_completato(self, identificativo: str) -> bool:
        with sessione() as s:
            riga = s.get(Promemoria, identificativo)
            if riga is None:
                return False
            riga.completed = True
            riga.completed_at = datetime.now().isoformat()
            return True


class DepositoLettureEnergia:
    """Lo storico dei contatori. Non eredita da `Deposito` perche' non ha un
    identificativo testuale: qui si interroga per intervallo di tempo, non
    per chiave, e le operazioni comuni non servirebbero a niente."""

    campi = ("id", "momento", "entity_id", "valore", "consumo", "fascia")

    def registra(
        self, entity_id: str, valore: float, consumo: float, fascia: str, momento: Optional[datetime] = None
    ) -> dict[str, Any]:
        with sessione() as s:
            riga = LetturaEnergia(
                entity_id=entity_id,
                valore=valore,
                consumo=consumo,
                fascia=fascia,
                momento=momento or datetime.now(timezone.utc),
            )
            s.add(riga)
            s.flush()
            return _come_dizionario(riga, self.campi)

    def ultima(self, entity_id: str) -> Optional[dict[str, Any]]:
        with sessione() as s:
            query = (
                select(LetturaEnergia)
                .where(LetturaEnergia.entity_id == entity_id)
                .order_by(LetturaEnergia.momento.desc())
                .limit(1)
            )
            riga = s.scalars(query).first()
            return _come_dizionario(riga, self.campi) if riga else None

    def fra(self, da: datetime, a: datetime, entity_id: Optional[str] = None) -> list[dict[str, Any]]:
        with sessione() as s:
            query = select(LetturaEnergia).where(LetturaEnergia.momento >= da, LetturaEnergia.momento < a)
            if entity_id:
                query = query.where(LetturaEnergia.entity_id == entity_id)
            query = query.order_by(LetturaEnergia.momento)
            return [_come_dizionario(r, self.campi) for r in s.scalars(query).all()]

    def entita_note(self) -> list[str]:
        with sessione() as s:
            return sorted({str(v) for v in s.scalars(select(LetturaEnergia.entity_id)).all()})

    def pulisci(self, prima_di: datetime) -> int:
        """Lo storico non cresce per sempre: chi guarda i consumi guarda al
        massimo l'anno, e una casa che scrive ogni ora fa quasi novemila
        righe l'anno per sensore."""
        with sessione() as s:
            esito = s.execute(delete(LetturaEnergia).where(LetturaEnergia.momento < prima_di))
            return int(getattr(esito, "rowcount", 0) or 0)


class DepositoListe(Deposito):
    modello = Lista
    campi = ("id", "nome", "creata_il")
    ordine = "nome"

    def per_nome(self, nome: str) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.scalars(select(Lista).where(Lista.nome == nome)).first()
            return _come_dizionario(riga, self.campi) if riga else None


class DepositoVociLista(Deposito):
    modello = VoceLista
    campi = ("id", "lista_id", "testo", "fatta", "autore", "aggiunta_il")
    ordine = "aggiunta_il"

    def della_lista(self, lista_id: str) -> list[dict[str, Any]]:
        with sessione() as s:
            query = select(VoceLista).where(VoceLista.lista_id == lista_id).order_by(VoceLista.aggiunta_il)
            return [_come_dizionario(r, self.campi) for r in s.scalars(query).all()]

    def svuota(self, lista_id: str, solo_fatte: bool = True) -> int:
        with sessione() as s:
            query = delete(VoceLista).where(VoceLista.lista_id == lista_id)
            if solo_fatte:
                query = query.where(VoceLista.fatta.is_(True))
            esito = s.execute(query)
            return int(getattr(esito, "rowcount", 0) or 0)


class DepositoEventi(Deposito):
    modello = EventoCalendario
    campi = ("id", "titolo", "inizio", "fine", "tutto_il_giorno", "luogo", "autore")
    ordine = "inizio"

    def fra(self, da: datetime, a: datetime) -> list[dict[str, Any]]:
        with sessione() as s:
            query = (
                select(EventoCalendario)
                .where(EventoCalendario.inizio < a)
                .where((EventoCalendario.fine.is_(None)) | (EventoCalendario.fine >= da))
                .order_by(EventoCalendario.inizio)
            )
            return [_come_dizionario(r, self.campi) for r in s.scalars(query).all()]


class DepositoScadenze(Deposito):
    modello = ScadenzaManutenzione
    campi = (
        "id",
        "titolo",
        "prossima",
        "ogni",
        "unita",
        "preavviso",
        "documento",
        "ultima_fatta",
        "promemoria_id",
    )
    ordine = "prossima"

    def entro(self, giorno: datetime) -> list[dict[str, Any]]:
        """Quelle da segnalare: scadute o dentro al preavviso.

        Il preavviso e' per riga — un bollo si annuncia con piu' anticipo di
        un filtro — quindi il confronto si fa qui e non nella query.
        """
        fuori = []
        for riga in self.elenco():
            prossima = riga.get("prossima")
            if not isinstance(prossima, datetime):
                continue
            mancanti = (prossima.date() - giorno.date()).days
            if mancanti < 0 or mancanti <= int(riga.get("preavviso") or 0):
                fuori.append(riga)
        return fuori


utenti = DepositoUtenti()
ruoli = DepositoRuoli()
fatti = DepositoFatti()
alias = DepositoAlias()
modalita = DepositoModalita()
fonti = DepositoFonti()
timer = DepositoTimer()
promemoria = DepositoPromemoria()
letture_energia = DepositoLettureEnergia()
liste = DepositoListe()
voci_lista = DepositoVociLista()
eventi_calendario = DepositoEventi()
scadenze = DepositoScadenze()

DEPOSITI: dict[str, Deposito] = {
    "users": utenti,
    "ruoli": ruoli,
    "knowledge": fatti,
    "device_aliases": alias,
    "modes": modalita,
    "sources": fonti,
    "timers": timer,
    "reminders": promemoria,
}
