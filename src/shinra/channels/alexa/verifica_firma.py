"""Verifica che una richiesta arrivi davvero da Amazon.

`/api/alexa` e' l'unico endpoint di Shinra raggiungibile da Internet, e finora
eseguiva comandi domotici senza controllare nulla: una POST JSON di dieci
righe da qualsiasi parte del mondo accendeva o spegneva la casa. La guida
all'installazione peggiorava le cose, consigliando di disattivare le
protezioni del reverse proxy proprio su quel percorso.

Amazon firma ogni richiesta. La verifica prescritta e' in quattro passi, e
saltarne uno la rende inutile:

1. l'URL della catena di certificati deve appartenere ad Amazon — altrimenti
   un attaccante indica la propria catena e firma quello che vuole;
2. il certificato deve essere valido nel tempo e riportare
   `echo-api.amazon.com` fra i nomi alternativi;
3. la firma deve corrispondere al corpo **grezzo** della richiesta, byte per
   byte: verificarla sul JSON riserializzato fallirebbe o, peggio,
   convaliderebbe un contenuto diverso da quello firmato;
4. il timestamp deve essere recente, altrimenti una richiesta intercettata
   resta riutilizzabile per sempre.

Riferimento: docs/backlog/v0.1.0/04-sec-02-firma-alexa.md
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from itertools import pairwise
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtensionOID, NameOID

logger = logging.getLogger("Shinra.Alexa.Firma")

HOST_ATTESO = "s3.amazonaws.com"
PERCORSO_ATTESO = "/echo.api/"
NOME_NEL_CERTIFICATO = "echo-api.amazon.com"
TOLLERANZA_SECONDI = 150
DIMENSIONE_MASSIMA_CATENA = 100_000
DURATA_CACHE_CERTIFICATI = 24 * 3600


class FirmaNonValida(Exception):
    """La richiesta non proviene da Amazon, o non e' piu' utilizzabile."""


_cache_certificati: dict[str, tuple[float, list[x509.Certificate]]] = {}


def valida_url_certificato(url: str) -> str:
    """L'URL deve appartenere ad Amazon.

    E' il controllo da cui dipendono tutti gli altri: senza, un attaccante
    indica la propria catena, firma la richiesta con la propria chiave e ogni
    verifica successiva darebbe esito positivo.
    """
    if not url:
        raise FirmaNonValida("Intestazione SignatureCertChainUrl assente.")

    pezzi = urlparse(url)

    if pezzi.scheme.lower() != "https":
        raise FirmaNonValida(f"Schema non ammesso: {pezzi.scheme!r}, atteso https.")
    if pezzi.hostname is None or pezzi.hostname.lower() != HOST_ATTESO:
        raise FirmaNonValida(f"Host non ammesso: {pezzi.hostname!r}.")
    if pezzi.port not in (None, 443):
        raise FirmaNonValida(f"Porta non ammessa: {pezzi.port}.")

    # Il confronto avviene sul percorso normalizzato: senza, un URL come
    # /echo.api/../altrove supererebbe un controllo di prefisso ingenuo.
    segmenti: list[str] = []
    for segmento in pezzi.path.split("/"):
        if segmento in ("", "."):
            continue
        if segmento == "..":
            if segmenti:
                segmenti.pop()
            continue
        segmenti.append(segmento)
    normalizzato = "/" + "/".join(segmenti)

    if not normalizzato.startswith(PERCORSO_ATTESO):
        raise FirmaNonValida(f"Percorso non ammesso: {pezzi.path!r}.")

    return url


async def scarica_catena(url: str, client: Optional[httpx.AsyncClient] = None) -> list[x509.Certificate]:
    """Scarica e analizza la catena, tenendola in cache per un giorno."""
    voce = _cache_certificati.get(url)
    if voce and time.time() - voce[0] < DURATA_CACHE_CERTIFICATI:
        return voce[1]

    proprio = client is None
    client = client or httpx.AsyncClient(timeout=6.0)
    try:
        risposta = await client.get(url)
        if risposta.status_code != 200:
            raise FirmaNonValida(f"Catena di certificati non scaricabile (HTTP {risposta.status_code}).")
        grezzo = risposta.content[:DIMENSIONE_MASSIMA_CATENA]
    except httpx.HTTPError as e:
        raise FirmaNonValida(f"Catena di certificati non raggiungibile: {e}") from e
    finally:
        if proprio:
            await client.aclose()

    try:
        catena = x509.load_pem_x509_certificates(grezzo)
    except ValueError as e:
        raise FirmaNonValida(f"Catena di certificati illeggibile: {e}") from e

    if not catena:
        raise FirmaNonValida("Catena di certificati vuota.")

    _cache_certificati[url] = (time.time(), catena)
    return catena


def valida_catena(catena: list[x509.Certificate], adesso: Optional[datetime] = None) -> x509.Certificate:
    """Controlla validita' temporale, nome atteso e legami della catena."""
    adesso = adesso or datetime.now(timezone.utc)
    foglia = catena[0]

    if foglia.not_valid_before_utc > adesso or foglia.not_valid_after_utc < adesso:
        raise FirmaNonValida("Certificato scaduto o non ancora valido.")

    try:
        san = foglia.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        nomi = san.value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        nomi = []

    if NOME_NEL_CERTIFICATO not in nomi:
        comune = [a.value for a in foglia.subject.get_attributes_for_oid(NameOID.COMMON_NAME)]
        if NOME_NEL_CERTIFICATO not in comune:
            raise FirmaNonValida(f"Il certificato non riporta {NOME_NEL_CERTIFICATO}.")

    # Ogni certificato deve essere firmato dal successivo. Non risaliamo fino
    # a una radice di sistema: l'ancora di fiducia qui e' l'URL, che solo
    # Amazon controlla (primo passo). Questo controllo impedisce che alla
    # catena venga accodato un certificato estraneo.
    for figlio, genitore in pairwise(catena):
        if figlio.issuer != genitore.subject:
            raise FirmaNonValida("Catena di certificati incoerente.")
        chiave = genitore.public_key()
        if not isinstance(chiave, rsa.RSAPublicKey):
            raise FirmaNonValida("Chiave del certificato non RSA.")
        try:
            chiave.verify(
                figlio.signature,
                figlio.tbs_certificate_bytes,
                padding.PKCS1v15(),
                figlio.signature_hash_algorithm,
            )
        except InvalidSignature as e:
            raise FirmaNonValida("Un certificato della catena non e' firmato dal successivo.") from e

    return foglia


def valida_firma(certificato: x509.Certificate, firma_base64: str, corpo: bytes) -> None:
    if not firma_base64:
        raise FirmaNonValida("Intestazione Signature assente.")
    try:
        firma = base64.b64decode(firma_base64, validate=True)
    except (ValueError, TypeError) as e:
        raise FirmaNonValida("Firma non decodificabile.") from e

    chiave = certificato.public_key()
    if not isinstance(chiave, rsa.RSAPublicKey):
        raise FirmaNonValida("Chiave del certificato non RSA.")

    try:
        # SHA-1 e' quello che Amazon usa per firmare le richieste Alexa: non
        # e' una scelta di Shinra, ed e' la ragione per cui i primi due passi
        # contano piu' di questo.
        # SHA-1 e' imposto dalla specifica Alexa: qui non e' una scelta, e
        # non indebolisce il controllo, perche' la fiducia poggia sull'URL
        # della catena e sul certificato, verificati prima di arrivare qui.
        chiave.verify(firma, corpo, padding.PKCS1v15(), hashes.SHA1())  # noqa: S303
    except InvalidSignature as e:
        raise FirmaNonValida("La firma non corrisponde al corpo della richiesta.") from e


def valida_timestamp(dati: dict[str, Any], adesso: Optional[datetime] = None) -> None:
    grezzo = (dati.get("request") or {}).get("timestamp")
    if not grezzo:
        raise FirmaNonValida("Timestamp assente nella richiesta.")
    try:
        momento = datetime.fromisoformat(str(grezzo).replace("Z", "+00:00"))
    except ValueError as e:
        raise FirmaNonValida(f"Timestamp illeggibile: {grezzo!r}") from e
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)

    scarto = abs((adesso or datetime.now(timezone.utc)) - momento).total_seconds()
    if scarto > TOLLERANZA_SECONDI:
        raise FirmaNonValida(f"Richiesta troppo vecchia o troppo nel futuro ({int(scarto)}s).")


def valida_skill_id(dati: dict[str, Any], atteso: Optional[str]) -> None:
    """Verifica che la richiesta venga dalla propria skill.

    Senza un identificativo configurato la richiesta viene **rifiutata**, non
    accettata: un controllo che si disattiva da solo quando non e' configurato
    non e' un controllo.
    """
    atteso = (atteso or "").strip()
    if not atteso:
        raise FirmaNonValida(
            "Nessun applicationId configurato: imposta SHINRA_ALEXA_SKILL_ID in .env "
            "con l'ID della tua skill (amzn1.ask.skill.xxxx)."
        )

    ricevuto = (
        ((dati.get("session") or {}).get("application") or {}).get("applicationId")
        or ((dati.get("context") or {}).get("System") or {}).get("application", {}).get("applicationId")
        or ""
    )
    if ricevuto != atteso:
        raise FirmaNonValida("La richiesta proviene da un'altra skill.")


async def verifica_richiesta(
    corpo: bytes,
    intestazioni: dict[str, str],
    dati: dict[str, Any],
    skill_id_atteso: Optional[str],
    client: Optional[httpx.AsyncClient] = None,
) -> None:
    """Solleva FirmaNonValida se la richiesta non e' autentica.

    L'ordine non e' casuale: prima i controlli che non costano nulla, per
    ultimo lo scaricamento della catena. Cosi' una raffica di richieste
    contraffatte non si trasforma in una raffica di richieste verso Amazon.
    """
    minuscole = {k.lower(): v for k, v in intestazioni.items()}

    valida_skill_id(dati, skill_id_atteso)
    valida_timestamp(dati)

    url = valida_url_certificato(minuscole.get("signaturecertchainurl", ""))
    catena = await scarica_catena(url, client=client)
    foglia = valida_catena(catena)
    valida_firma(foglia, minuscole.get("signature", ""), corpo)
