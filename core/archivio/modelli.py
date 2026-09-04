"""Le tabelle di Shinra.

**Sui nomi delle colonne.** Il progetto scrive in italiano il codice nuovo,
ma qui i nomi dei campi restano quelli di oggi — `text`, `category`,
`enabled`, `entity_id` — perche' non sono una scelta di stile: sono il
contratto che l'interfaccia web, le rotte HTTP e i file JSON esistenti gia'
usano. Tradurli qui vorrebbe dire aggiungere uno strato di conversione fra
database e API, cioe' un punto in piu' dove sbagliare durante una migrazione
che deve andare bene la prima volta. Le tabelle nuove, che non hanno un
passato, sono in italiano.

**Sugli identificativi.** Restano stringhe (`k_3f9a`, `timer_ab12`, `alessio`)
invece di diventare interi: sono gia' scritti nei file JSON, nei job dello
scheduler e nei cookie di sessione. Cambiarli renderebbe la migrazione una
riscrittura invece di una copia.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def adesso() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Utente(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="adult")
    age_group: Mapped[str] = mapped_column(String(32), default="adult")
    gender: Mapped[str] = mapped_column(String(32), default="unspecified")
    avatar_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Sempre cifrato: e' la regola stabilita dalla issue #3, non un'opzione.
    pin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_news_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    restricted_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    aggiornato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso, onupdate=adesso)


class Fatto(Base):
    """Un'informazione sulla casa, imparata o inserita a mano."""

    __tablename__ = "knowledge"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="generale", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)


class Alias(Base):
    """Il nome con cui una persona chiama un dispositivo di Home Assistant."""

    __tablename__ = "device_aliases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alias: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    room: Mapped[Optional[str]] = mapped_column(String(80), default="")
    domain: Mapped[Optional[str]] = mapped_column(String(40), default="light")


class Modalita(Base):
    """Una routine: «modalita' cinema» e le azioni che esegue."""

    __tablename__ = "modes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(40), default="zap")
    trigger_phrases: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[Optional[str]] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class Fonte(Base):
    """Una fonte di notizie."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="generale", index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Timer(Base):
    __tablename__ = "timers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(160), default="Timer")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[float] = mapped_column(Float, default=0.0)
    expires_at: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    # Nessun vincolo verso users: un timer creato da un ospite non registrato
    # deve sopravvivere, e cancellare una persona non deve far sparire i
    # timer che ha in corso in cucina.
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class Promemoria(Base):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class VoceRegistro(Base):
    """Una riga del registro delle azioni: chi ha fatto cosa, e com'e' andata.

    La tabella nasce qui, vuota, perche' lo schema iniziale la contenga: farla
    nascere dopo significherebbe una seconda migrazione sul database di una
    casa gia' in funzione. A scriverci sara' la issue #15; fino ad allora
    resta a zero righe, e si vede.
    """

    __tablename__ = "registro_azioni"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    momento: Mapped[datetime] = mapped_column(DateTime, default=adesso, index=True)
    attore: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    canale: Mapped[str] = mapped_column(String(32), default="")
    azione: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dettagli: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    esito: Mapped[str] = mapped_column(String(32), default="")
