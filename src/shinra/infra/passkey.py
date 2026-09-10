"""L'involucro attorno a `py_webauthn`.

Tutto quello che tocca la crittografia sta qui, e nient'altro: cosi' il
servizio sopra parla di persone e credenziali invece di CBOR e COSE, e il
giorno in cui la libreria cambia si riscrive un file solo.

**E' una dipendenza facoltativa.** Se `webauthn` non e' installato, le
passkey non ci sono e il PIN continua a funzionare — che e' il criterio
della scheda: chi non le vuole non perde niente. Un `import` in cima al file
farebbe cadere l'avvio dell'intero server per una funzione che si puo' non
usare.

Riferimento: issue #48.
"""

from __future__ import annotations

import base64
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("Shinra.Passkey")

# Trentadue byte casuali: e' la lunghezza raccomandata, e la sfida serve solo
# a rendere irripetibile una firma.
BYTE_SFIDA = 32


class VerificaFallita(Exception):
    """La firma non torna. Il motivo resta nel log, non nella risposta."""


@dataclass(frozen=True)
class Registrata:
    """Cosa si e' imparato da una registrazione riuscita."""

    credenziale_id: str
    chiave_pubblica: str
    contatore: int
    tipo_dispositivo: str


@dataclass(frozen=True)
class Verificata:
    """Cosa si e' imparato da un accesso riuscito."""

    credenziale_id: str
    contatore: int


def libreria() -> Optional[Any]:
    """Il modulo `webauthn`, o `None` se non e' installato."""
    try:
        import webauthn
    except ImportError:  # pragma: no cover - dipende dall'ambiente
        return None
    return webauthn


def disponibile() -> bool:
    return libreria() is not None


def _b64(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).decode().rstrip("=")


def _da_b64(testo: str) -> bytes:
    riempimento = "=" * (-len(testo) % 4)
    return base64.urlsafe_b64decode(testo + riempimento)


def nuova_sfida() -> bytes:
    return secrets.token_bytes(BYTE_SFIDA)


def opzioni_registrazione(
    rp_id: str,
    nome_casa: str,
    utente_id: str,
    nome_utente: str,
    sfida: bytes,
    gia_registrate: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Le opzioni che il browser passa a `navigator.credentials.create()`.

    `resident_key` richiesta e `user_verification` richiesta insieme sono cio'
    che realizza il criterio della scheda — «si accede con Face ID o impronta
    senza digitare nulla». La prima fa si' che la credenziale sia
    *individuabile*, cioe' che il browser sappia proporla senza che si dica
    prima chi si e'; la seconda che l'autenticatore chieda comunque il volto,
    l'impronta o il codice del dispositivo, e non si limiti a essere presente.

    `gia_registrate` evita che lo stesso dispositivo registri due passkey per
    la stessa persona: senza, l'elenco si riempie di righe indistinguibili e
    revocare quella giusta diventa un indovinello.
    """
    import json

    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    escluse = [PublicKeyCredentialDescriptor(id=_da_b64(c)) for c in (gia_registrate or [])]

    opzioni = generate_registration_options(
        rp_id=rp_id,
        rp_name=nome_casa,
        user_id=utente_id.encode(),
        user_name=nome_utente,
        user_display_name=nome_utente,
        challenge=sfida,
        exclude_credentials=escluse,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return json.loads(options_to_json(opzioni))


def verifica_registrazione(credenziale: dict[str, Any], sfida: bytes, rp_id: str, origine: str) -> Registrata:
    """Controlla la risposta del browser e ne estrae cosa salvare."""
    from webauthn import verify_registration_response
    from webauthn.helpers.exceptions import WebAuthnException

    try:
        esito = verify_registration_response(
            credential=credenziale,
            expected_challenge=sfida,
            expected_rp_id=rp_id,
            expected_origin=origine,
            require_user_verification=True,
        )
    except (WebAuthnException, ValueError, KeyError) as errore:
        # Il dettaglio nel log, non nella risposta: a chi prova a indovinare
        # non si spiega quale pezzo non torna.
        logger.warning("Registrazione passkey rifiutata: %s", errore)
        raise VerificaFallita("La registrazione non e' stata accettata.") from errore

    return Registrata(
        credenziale_id=_b64(esito.credential_id),
        chiave_pubblica=_b64(esito.credential_public_key),
        contatore=int(esito.sign_count or 0),
        tipo_dispositivo=getattr(esito.credential_device_type, "value", "") or "",
    )


def opzioni_accesso(rp_id: str, sfida: bytes) -> dict[str, Any]:
    """Le opzioni per `navigator.credentials.get()`.

    Nessun `allow_credentials`: l'elenco delle credenziali di una persona
    direbbe a chiunque apra la pagina chi vive in questa casa e quanti
    dispositivi ha. Le passkey individuabili non ne hanno bisogno — e' il
    browser a sapere quale offrire.
    """
    import json

    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement

    opzioni = generate_authentication_options(
        rp_id=rp_id,
        challenge=sfida,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(opzioni))


def verifica_accesso(
    credenziale: dict[str, Any],
    sfida: bytes,
    rp_id: str,
    origine: str,
    chiave_pubblica: str,
    contatore: int,
) -> Verificata:
    from webauthn import verify_authentication_response
    from webauthn.helpers.exceptions import WebAuthnException

    try:
        esito = verify_authentication_response(
            credential=credenziale,
            expected_challenge=sfida,
            expected_rp_id=rp_id,
            expected_origin=origine,
            credential_public_key=_da_b64(chiave_pubblica),
            credential_current_sign_count=contatore,
            require_user_verification=True,
        )
    except (WebAuthnException, ValueError, KeyError) as errore:
        logger.warning("Accesso con passkey rifiutato: %s", errore)
        raise VerificaFallita("La passkey non e' stata accettata.") from errore

    return Verificata(
        credenziale_id=_b64(esito.credential_id),
        contatore=int(esito.new_sign_count or 0),
    )


def identificativo_dalla_risposta(credenziale: dict[str, Any]) -> str:
    """L'identificativo della credenziale, per cercarla prima di verificarla.

    Serve perche' senza `allow_credentials` non si sa chi sta entrando finche'
    non si guarda cosa ha mandato: la chiave pubblica con cui verificare la
    firma si trova a partire da qui.
    """
    return str(credenziale.get("id") or credenziale.get("rawId") or "")
