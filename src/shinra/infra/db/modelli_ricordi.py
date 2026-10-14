"""I ricordi e i loro vettori (#245). In un file loro: `modelli.py` ha il suo tetto di righe."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from shinra.infra.db.base import Base, DataOra, adesso

# I campi di un ricordo cosi' come li vedono il deposito, le rotte e il salvataggio.
CAMPI_DEL_RICORDO = (
    "id",
    "text",
    "category",
    "enabled",
    "proprietario",
    "origine",
    "importanza",
    "ultimo_uso",
    "usi",
    "stato",
    "aggiornato_il",
    "luogo_id",
)


class Fatto(Base):
    """Un ricordo: un'informazione sulla casa o su una persona, imparata o inserita a mano.

    Un ricordo ha un **proprietario** (vuoto = della casa, visibile a chi puo' leggere la conoscenza; altrimenti l'id del
    profilo, e lo vede solo lui: ADR 0009), un'**origine**, un'**importanza**, e una **storia d'uso** (quando e quante
    volte e' servito) che il recupero usera' per ordinarli. Lo **stato** dice se e' attivo, solo proposto (da una persona
    o dal sogno notturno: non entra nel prompt finche' non e' accettato) o archiviato.
    """

    __tablename__ = "knowledge"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="generale", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    # Vuoto: della casa. Altrimenti l'identificativo del profilo a cui appartiene (ADR 0009).
    proprietario: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    # manuale, intervista, conversazione, sogno, importato.
    origine: Mapped[str] = mapped_column(String(16), default="manuale", server_default="manuale")
    # Da 1 (poco) a 5 (molto): pesa nell'ordine in cui si scelgono i ricordi per il prompt.
    importanza: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    ultimo_uso: Mapped[Optional[datetime]] = mapped_column(DataOra, nullable=True)
    usi: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # attivo, proposto, archiviato. Un ricordo non attivo non entra mai nel prompt.
    stato: Mapped[str] = mapped_column(String(12), default="attivo", server_default="attivo")
    aggiornato_il: Mapped[Optional[datetime]] = mapped_column(DataOra, nullable=True, onupdate=adesso)
    # Il luogo a cui il ricordo si riferisce (#345); vuoto: a nessuno in particolare.
    luogo_id: Mapped[str] = mapped_column(String(32), default="", server_default="")


class EmbeddingFatto(Base):
    """Il vettore di un fatto, con l'impronta del testo da cui e' nato.

    L'impronta e' la parte che fa lavorare il ricalcolo da solo: se il testo
    del fatto cambia, l'impronta salvata non corrisponde piu' e il vettore
    viene rifatto — senza che nessuno debba ricordarsi di chiamare qualcosa
    quando modifica un fatto. Un vettore vecchio non da' errore: da' risposte
    sbagliate, che e' peggio.

    Anche il nome del modello e' salvato: cambiare modello di embedding
    cambia lo spazio vettoriale, e confrontare vettori di due modelli diversi
    produce numeri che sembrano punteggi e non lo sono.

    Riferimento: issue #32.
    """

    __tablename__ = "embedding_fatti"

    fatto_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vettore: Mapped[list[Any]] = mapped_column(JSON, default=list)
    modello: Mapped[str] = mapped_column(String(120), default="")
    impronta: Mapped[str] = mapped_column(String(64), default="", index=True)
    calcolato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
