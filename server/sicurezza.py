"""Autenticazione: identita' per persona, sessioni, e il cancello sulle rotte.

Prima di questo modulo `is_authenticated()` era invocata in **un solo endpoint
su trentanove**: chiunque fosse sulla rete di casa poteva comandare l'impianto
e leggere l'anagrafica della famiglia con una `curl`.

Due cambiamenti sostanziali:

1. **Protetto per difetto.** La protezione e' una dipendenza applicata
   all'intero router. Un endpoint nuovo nasce chiuso; per aprirlo bisogna
   dichiararlo in `ROTTE_PUBBLICHE`, e un test fallisce se qualcuno se ne
   dimentica.
2. **Un PIN per persona, non uno per la casa.** La sessione porta con se'
   l'identita' reale, non una scelta da menu a tendina. E' il fondamento su
   cui poggeranno i permessi della v0.2.0: un permesso vale quanto l'identita'
   su cui si basa.

Riferimenti: docs/backlog/v0.1.0/03-sec-01-auth-su-tutti-gli-endpoint.md,
docs/adr/0004-identita-ruoli-e-permessi.md
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status

from config.settings import settings
from core.user_manager import UserProfile, user_manager

logger = logging.getLogger("Shinra.Sicurezza")

NOME_COOKIE = "shinra_sessione"
INTESTAZIONE_LEGACY = "x-shinra-auth"

DURATA_SESSIONE = 30 * 24 * 3600  # 30 giorni — vedi ADR 0004
MAX_SESSIONI = 200
TENTATIVI_MAX = 5
FINESTRA_TENTATIVI = 300  # 5 minuti

# Rotte raggiungibili senza sessione. Ogni voce e' una scelta deliberata:
# aggiungerne una significa aprire un varco, e il test di inventario in
# tests/unit/test_autenticazione.py obbliga a passare di qui.
ROTTE_PUBBLICHE: dict[str, str] = {
    "/": "guscio della dashboard; il blocco lato server e' la issue #5",
    "/health": "sonda di liveness, nessuna informazione nel corpo",
    "/api/auth/status": "dice se serve autenticarsi — deve funzionare da sconosciuti",
    "/api/auth/login": "l'accesso stesso",
    "/api/auth/logout": "chiudere una sessione non richiede di averne una valida",
    "/api/auth/profili": "elenco dei profili per la schermata di accesso, senza dati sensibili",
    "/api/alexa": "protetta dalla firma Amazon, non dalla sessione — issue #4",
}

# --------------------------------------------------------------------------
# PIN
# --------------------------------------------------------------------------

ITERAZIONI_PBKDF2 = 240_000
PREFISSO_HASH = "pbkdf2_sha256"


def cifra_pin(pin: str) -> str:
    """Trasforma un PIN nel suo hash con sale casuale.

    PBKDF2-HMAC-SHA256 dalla libreria standard: nessuna dipendenza nuova per
    una funzione che deve esistere prima di poter salvare un PIN per persona.
    """
    sale = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), sale.encode(), ITERAZIONI_PBKDF2)
    return f"{PREFISSO_HASH}${ITERAZIONI_PBKDF2}${sale}${digest.hex()}"


def verifica_pin(pin: str, cifrato: Optional[str]) -> bool:
    """Confronto a tempo costante fra un PIN e il suo hash."""
    if not cifrato or not pin:
        return False
    try:
        algoritmo, iterazioni, sale, atteso = cifrato.split("$")
        if algoritmo != PREFISSO_HASH:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), sale.encode(), int(iterazioni))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), atteso)


def e_cifrato(valore: Optional[str]) -> bool:
    return bool(valore) and str(valore).startswith(f"{PREFISSO_HASH}$")


# --------------------------------------------------------------------------
# Sessioni
# --------------------------------------------------------------------------


@dataclass
class Sessione:
    token: str
    user_id: str
    creata_il: float
    vista_il: float


@dataclass
class _Stato:
    sessioni: dict[str, Sessione] = field(default_factory=dict)
    tentativi: dict[str, list[float]] = field(default_factory=dict)


_stato = _Stato()


def _firma(valore: str) -> str:
    segreto = (settings.security.session_secret or "").encode() or b"shinra-senza-segreto"
    return hmac.new(segreto, valore.encode(), hashlib.sha256).hexdigest()[:32]


def crea_sessione(user_id: str) -> str:
    """Genera un token di sessione firmato.

    La firma non protegge da chi ruba il token — per quello serve il cookie
    HttpOnly — ma rende inutile provare a indovinarne uno: un valore non
    firmato con il segreto di questa installazione viene scartato senza
    nemmeno cercarlo fra le sessioni.
    """
    ora = time.time()
    _pota_sessioni(ora)
    grezzo = secrets.token_urlsafe(32)
    token = f"{grezzo}.{_firma(grezzo)}"
    _stato.sessioni[token] = Sessione(token=token, user_id=user_id, creata_il=ora, vista_il=ora)
    return token


def _firma_valida(token: str) -> bool:
    grezzo, _, firma = token.rpartition(".")
    if not grezzo or not firma:
        return False
    return hmac.compare_digest(_firma(grezzo), firma)


def _pota_sessioni(ora: float) -> None:
    scadute = [t for t, s in _stato.sessioni.items() if ora - s.creata_il >= DURATA_SESSIONE]
    for t in scadute:
        _stato.sessioni.pop(t, None)
    # Limite di sicurezza: senza, una raffica di accessi falliti-poi-riusciti
    # farebbe crescere il dizionario senza fine.
    if len(_stato.sessioni) > MAX_SESSIONI:
        piu_vecchie = sorted(_stato.sessioni.values(), key=lambda s: s.vista_il)
        for s in piu_vecchie[: len(_stato.sessioni) - MAX_SESSIONI]:
            _stato.sessioni.pop(s.token, None)


def sessione_valida(token: Optional[str]) -> Optional[Sessione]:
    if not token or not _firma_valida(token):
        return None
    sessione = _stato.sessioni.get(token)
    if not sessione:
        return None
    ora = time.time()
    if ora - sessione.creata_il >= DURATA_SESSIONE:
        _stato.sessioni.pop(token, None)
        return None
    sessione.vista_il = ora
    return sessione


def chiudi_sessione(token: Optional[str]) -> None:
    if token:
        _stato.sessioni.pop(token, None)


def chiudi_sessioni_di(user_id: str) -> int:
    """Invalida tutte le sessioni di un utente. Usata al cambio di PIN."""
    da_chiudere = [t for t, s in _stato.sessioni.items() if s.user_id == user_id]
    for t in da_chiudere:
        _stato.sessioni.pop(t, None)
    return len(da_chiudere)


def azzera_stato() -> None:
    """Solo per i test."""
    _stato.sessioni.clear()
    _stato.tentativi.clear()


# --------------------------------------------------------------------------
# Limitazione dei tentativi
# --------------------------------------------------------------------------


def _chiave_client(request: Request) -> str:
    """Identifica il client per la limitazione dei tentativi.

    `X-Forwarded-For` viene letto **solo** se la richiesta arriva da un proxy
    dichiarato fidato in configurazione. E' un'intestazione che il client
    scrive: fidarsene sempre permetterebbe a chi attacca di azzerare il
    contatore dei tentativi cambiando un valore a ogni richiesta. Non fidarsene
    mai, dietro un reverse proxy, produce il difetto opposto — il quinto
    tentativo sbagliato di uno sconosciuto blocca il proprietario di casa,
    perche' per il server hanno lo stesso indirizzo.
    """
    osservato = request.client.host if request.client else "sconosciuto"

    fidati = settings.security.trusted_proxies or []
    if osservato not in fidati:
        return osservato

    inoltrato = request.headers.get("x-forwarded-for", "")
    if not inoltrato:
        return osservato

    # Il primo della lista e' il client originale; gli altri sono i proxi
    # attraversati. Si prende quello e si scarta il resto.
    primo = inoltrato.split(",")[0].strip()
    return primo or osservato


def tentativi_esauriti(request: Request) -> bool:
    ora = time.time()
    chiave = _chiave_client(request)
    recenti = [t for t in _stato.tentativi.get(chiave, []) if ora - t < FINESTRA_TENTATIVI]
    _stato.tentativi[chiave] = recenti
    return len(recenti) >= TENTATIVI_MAX


def registra_tentativo_fallito(request: Request) -> None:
    chiave = _chiave_client(request)
    _stato.tentativi.setdefault(chiave, []).append(time.time())


def azzera_tentativi(request: Request) -> None:
    _stato.tentativi.pop(_chiave_client(request), None)


# --------------------------------------------------------------------------
# Cookie
# --------------------------------------------------------------------------


def imposta_cookie_sessione(response: Response, token: str) -> None:
    response.set_cookie(
        key=NOME_COOKIE,
        value=token,
        max_age=DURATA_SESSIONE,
        httponly=True,  # non leggibile da JavaScript
        samesite="lax",
        secure=False,  # in casa si accede anche in HTTP sulla rete locale
        path="/",
    )


def rimuovi_cookie_sessione(response: Response) -> None:
    response.delete_cookie(key=NOME_COOKIE, path="/")


def token_dalla_richiesta(request: Request) -> Optional[str]:
    """Cookie prima, intestazione poi.

    L'intestazione resta accettata perche' l'interfaccia attuale la usa e i
    client esterni ne hanno bisogno; il cookie e' preferibile perche' non e'
    leggibile da JavaScript.
    """
    dal_cookie = request.cookies.get(NOME_COOKIE)
    if dal_cookie:
        return dal_cookie
    grezza = request.headers.get(INTESTAZIONE_LEGACY)
    if grezza:
        return grezza.replace("Bearer ", "").strip()
    return None


# --------------------------------------------------------------------------
# Dipendenze FastAPI
# --------------------------------------------------------------------------


def autenticazione_attiva() -> bool:
    """L'autenticazione e' attiva se richiesta e se qualcuno puo' accedere.

    Senza almeno un PIN configurato, imporla chiuderebbe fuori tutti: in una
    casa questo significa nessun controllo su luci e riscaldamento. Il
    controllo d'avvio segnala la situazione a voce alta invece di creare un
    sistema inaccessibile.
    """
    if not settings.security.auth_enabled:
        return False
    # Conta solo i PIN in formato valido. Un valore in chiaro rimasto da una
    # versione precedente non verra' mai riconosciuto dal confronto: contarlo
    # renderebbe la casa chiusa a tutti, proprietario compreso.
    return any(e_cifrato(u.pin) for u in user_manager.get_users())


def utente_corrente(request: Request) -> Optional[UserProfile]:
    """Il profilo della sessione, o None. Non solleva eccezioni."""
    if not autenticazione_attiva():
        return None
    sessione = sessione_valida(token_dalla_richiesta(request))
    if not sessione:
        return None
    return user_manager.get_user_by_id(sessione.user_id)


def richiedi_autenticazione(request: Request) -> Optional[UserProfile]:
    """Dipendenza da applicare a ogni rotta che non sia esplicitamente pubblica."""
    if not autenticazione_attiva():
        return None

    sessione = sessione_valida(token_dalla_richiesta(request))
    if not sessione:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessione assente o scaduta. Accedi con il tuo PIN.",
        )

    profilo = user_manager.get_user_by_id(sessione.user_id)
    if not profilo:
        # Il profilo e' stato cancellato mentre la sessione era aperta.
        chiudi_sessione(sessione.token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Il profilo di questa sessione non esiste piu'.",
        )
    return profilo


def richiedi_amministratore(
    profilo: Optional[UserProfile] = Depends(richiedi_autenticazione),
) -> Optional[UserProfile]:
    """Riservato all'amministratore.

    Provvisorio: i ruoli veri arrivano con la issue #19 della v0.2.0. Qui
    protegge le operazioni piu' distruttive — cancellare utenti, cambiare la
    configurazione — senza aspettare quel lavoro.
    """
    if profilo is None:  # autenticazione non attiva
        return None
    if profilo.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Questa operazione e' riservata all'amministratore.",
        )
    return profilo
