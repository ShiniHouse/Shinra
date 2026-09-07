"""Dispositivi fidati: non chiedere il PIN a ogni apertura del telefono.

Un PIN per persona rende i permessi reali, ma su un telefono diventa un
fastidio quotidiano — e una protezione fastidiosa viene disattivata. A quel
punto la casa e' aperta come prima, con in piu' l'illusione di essere
protetta. Questo modulo e' cio' che rende sopportabile la protezione della
issue #3, ed e' la ragione per cui esiste: e' un compromesso deliberato fra
sicurezza e uso quotidiano, non una scorciatoia.

Due scelte che contano:

**Della credenziale si conserva solo l'impronta.** Come per i PIN. Se un
giorno il database finisse dove non deve, quelle righe non aprirebbero
nessuna casa: l'originale ce l'ha soltanto il dispositivo, in un cookie che
JavaScript non puo' leggere.

**Un dispositivo fidato identifica, non promuove.** Dice «questo e' il
telefono di Thomas», e Thomas resta un ragazzo con i permessi da ragazzo.

Riferimento: issue #20, ADR 0004.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("Shinra.Dispositivi")

NOME_COOKIE = "shinra_dispositivo"
DURATA_GIORNI = 30


def _impronta(credenziale: str) -> str:
    """SHA-256 senza sale ne' iterazioni, e va bene cosi'.

    Un PIN e' corto e indovinabile, quindi va rallentato con PBKDF2. Questa
    credenziale sono 256 bit casuali: non si indovina, e l'unica cosa che
    serve e' non tenerla in chiaro.
    """
    return hashlib.sha256(credenziale.encode()).hexdigest()


def _adesso() -> datetime:
    return datetime.now(timezone.utc)


def _senza_fuso(momento: datetime) -> datetime:
    """SQLite restituisce datetime senza fuso: si confrontano fra pari."""
    return momento.replace(tzinfo=None) if momento.tzinfo else momento


def ricorda(user_id: str, nome: str = "", indirizzo: str = "", firma=None) -> str:
    """Registra un dispositivo e restituisce la credenziale, una volta sola.

    `firma` la avvolge come si fa con i token di sessione, cosi' una
    credenziale inventata viene scartata senza nemmeno cercarla nel
    database. Si conserva l'impronta della credenziale gia' firmata: e'
    quella che il dispositivo rimandera' indietro.
    """
    from core.archivio.modelli import DispositivoFidato
    from core.archivio.motore import sessione

    credenziale = secrets.token_urlsafe(32)
    if firma is not None:
        credenziale = firma(credenziale)
    with sessione() as s:
        s.add(
            DispositivoFidato(
                id=uuid.uuid4().hex[:16],
                impronta=_impronta(credenziale),
                user_id=user_id,
                nome=(nome or "Dispositivo").strip()[:120],
                ultimo_indirizzo=indirizzo or None,
            )
        )
    logger.info("Dispositivo fidato registrato per %s: %s", user_id, nome or "senza nome")
    return credenziale


def riconosci(credenziale: Optional[str], indirizzo: str = "") -> Optional[str]:
    """Se la credenziale e' valida restituisce l'identificativo dell'utente.

    Ogni riconoscimento rinnova la scadenza: un telefono usato tutti i giorni
    non chiede mai il PIN, uno lasciato in un cassetto per un mese lo
    richiede. E' la differenza fra ricordare un dispositivo e fidarsene per
    sempre.
    """
    if not credenziale:
        return None

    from sqlalchemy import select

    from core.archivio.modelli import DispositivoFidato
    from core.archivio.motore import sessione

    impronta = _impronta(credenziale)
    limite = _senza_fuso(_adesso() - timedelta(days=DURATA_GIORNI))

    with sessione() as s:
        riga = s.scalars(select(DispositivoFidato).where(DispositivoFidato.impronta == impronta)).first()
        if riga is None:
            return None
        if _senza_fuso(riga.ultimo_uso) < limite:
            s.delete(riga)
            logger.info("Dispositivo fidato scaduto e rimosso: %s", riga.nome)
            return None
        riga.ultimo_uso = _adesso()
        if indirizzo:
            riga.ultimo_indirizzo = indirizzo
        return riga.user_id


def elenco(user_id: Optional[str] = None) -> list[dict[str, Any]]:
    """I dispositivi ricordati. Mai l'impronta: non serve a chi guarda."""
    from sqlalchemy import select

    from core.archivio.modelli import DispositivoFidato
    from core.archivio.motore import sessione

    query = select(DispositivoFidato).order_by(DispositivoFidato.ultimo_uso.desc())
    if user_id:
        query = query.where(DispositivoFidato.user_id == user_id)

    with sessione() as s:
        return [
            {
                "id": d.id,
                "nome": d.nome,
                "user_id": d.user_id,
                "creato_il": d.creato_il.isoformat(),
                "ultimo_uso": d.ultimo_uso.isoformat(),
                "ultimo_indirizzo": d.ultimo_indirizzo,
            }
            for d in s.scalars(query).all()
        ]


def revoca(identificativo: str) -> bool:
    from core.archivio.modelli import DispositivoFidato
    from core.archivio.motore import sessione

    with sessione() as s:
        riga = s.get(DispositivoFidato, identificativo)
        if riga is None:
            return False
        s.delete(riga)
    return True


def revoca_tutti(user_id: Optional[str] = None, tranne_credenziale: Optional[str] = None) -> int:
    """Il telefono perso.

    `tranne_credenziale` serve al cambio di PIN: si revocano tutti gli altri
    dispositivi, ma non quello da cui si sta cambiando — altrimenti l'unica
    conseguenza visibile di aver cambiato il PIN sarebbe doverlo ridigitare
    subito, e la funzione verrebbe evitata.
    """
    from sqlalchemy import select

    from core.archivio.modelli import DispositivoFidato
    from core.archivio.motore import sessione

    risparmiata = _impronta(tranne_credenziale) if tranne_credenziale else None
    query = select(DispositivoFidato)
    if user_id:
        query = query.where(DispositivoFidato.user_id == user_id)

    with sessione() as s:
        righe = [d for d in s.scalars(query).all() if d.impronta != risparmiata]
        for riga in righe:
            s.delete(riga)
        return len(righe)
