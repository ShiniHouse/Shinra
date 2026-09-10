"""Le decisioni che una passkey richiede, prima di chiamare una libreria.

WebAuthn e' quasi tutto crittografia, e quella la fa `py_webauthn`. Quello
che resta — e che sta qui — sono le poche domande a cui deve rispondere chi
la installa in casa, e che nessuna libreria puo' rispondere al posto suo.

**Su quale dominio vale questa credenziale.** L'`rp_id` e' il dominio a cui
l'autenticatore lega la chiave: e' l'autenticatore stesso a rifiutarsi di
firmare per un dominio diverso, ed e' questo — non un controllo lato server —
che rende una passkey immune al phishing. Sbagliare l'`rp_id` non produce un
buco: produce credenziali che non funzionano piu'.

**Perche' a volte non si puo' proprio.** WebAuthn esiste solo in un contesto
sicuro, e l'`rp_id` dev'essere un nome di dominio: `http://192.168.1.50:8000`
non ha ne' l'uno ne' l'altro. In una casa questo e' il caso *normale*, non
l'eccezione, e la risposta giusta e' dirlo con chiarezza invece di mostrare un
pulsante che fallisce con un errore del browser.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Optional

# Un contesto sicuro secondo i browser: HTTPS ovunque, piu' `localhost` in
# chiaro. E' la stessa regola che vale per il service worker delle notifiche.
LOCALI = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})

# Perche' le passkey non sono disponibili. Ognuno ha un rimedio diverso, e
# dirlo e' l'unica cosa utile che si possa fare a chi ne ha bisogno.
DISPONIBILI = "disponibili"
SENZA_HTTPS = "senza_https"
INDIRIZZO_NUMERICO = "indirizzo_numerico"
LIBRERIA_ASSENTE = "libreria_assente"

# Quanto resta valida una sfida. Sessanta secondi bastano a poggiare un dito
# sul lettore; un'ora basterebbe a chi ha intercettato la sfida a costruirci
# qualcosa sopra con calma.
DURATA_SFIDA = 120.0

NOME_PREDEFINITO = "Passkey"
NOME_MASSIMO = 60


@dataclass(frozen=True)
class Contesto:
    """Dove sta girando Shinra, per quanto riguarda WebAuthn."""

    rp_id: str
    origine: str
    motivo: str = DISPONIBILI

    @property
    def disponibile(self) -> bool:
        return self.motivo == DISPONIBILI


def _senza_porta(host: str) -> str:
    """`casa.example:8443` -> `casa.example`, `[::1]:8000` -> `[::1]`."""
    pulito = (host or "").strip().lower()
    if pulito.startswith("["):  # IPv6 fra parentesi quadre
        chiusura = pulito.find("]")
        return pulito[: chiusura + 1] if chiusura != -1 else pulito
    return pulito.split(":", 1)[0]


def e_indirizzo_numerico(host: str) -> bool:
    """Vero per `192.168.1.50` e `[::1]`, falso per `casa.example`.

    Un indirizzo numerico non e' un nome di dominio, e l'`rp_id` dev'essere un
    nome di dominio: non e' una scelta di questo progetto, e' la specifica.
    """
    nudo = _senza_porta(host).strip("[]")
    if not nudo:
        return False
    try:
        ipaddress.ip_address(nudo)
    except ValueError:
        return False
    return True


def leggi_contesto(
    schema: str,
    host: str,
    rp_id_configurato: str = "",
    origine_configurata: str = "",
    libreria_presente: bool = True,
) -> Contesto:
    """Da com'e' arrivata la richiesta a «si puo', e con quale dominio».

    Per difetto il dominio si ricava dalla richiesta, perche' in una casa
    nessuno lo configurera' mai e una funzione che va configurata per
    funzionare e' una funzione che non si usa. Chi ha un dominio stabile puo'
    fissarlo (`security.passkey_rp_id`), ed e' consigliato: se la dashboard si
    raggiunge a piu' nomi — `casa.example` da fuori, `shinra.local` da dentro
    — le passkey registrate sull'uno non funzionano sull'altro, e senza un
    valore fisso l'errore si presenta come «la passkey non e' riconosciuta».

    Ricavarlo dalla richiesta non e' un buco: e' l'autenticatore a legare la
    credenziale a un `rp_id` e a rifiutarsi di firmare per un altro, quindi un
    sito ostile su un dominio diverso non ottiene una firma valida comunque.
    Il controllo dell'origine lato server e' il secondo strato, non il primo.
    """
    if not libreria_presente:
        return Contesto("", "", LIBRERIA_ASSENTE)

    schema = (schema or "http").strip().lower()
    dominio = _senza_porta(host)
    autorita = (host or "").strip().lower()

    if e_indirizzo_numerico(host):
        return Contesto("", "", INDIRIZZO_NUMERICO)

    if schema != "https" and dominio not in LOCALI:
        return Contesto("", "", SENZA_HTTPS)

    rp_id = (rp_id_configurato or "").strip().lower() or dominio
    origine = (origine_configurata or "").strip() or f"{schema}://{autorita}"

    if not rp_id:
        return Contesto("", "", SENZA_HTTPS)

    return Contesto(rp_id, origine, DISPONIBILI)


def spiega(motivo: str) -> str:
    """Cosa dire a chi vede il pulsante spento. Ogni motivo ha un rimedio."""
    if motivo == INDIRIZZO_NUMERICO:
        return (
            "Le passkey hanno bisogno di un nome di dominio: a un indirizzo numerico "
            "il browser non le offre. Dai un nome alla casa — anche solo «shinra.local» "
            "sul router — e raggiungila da li'."
        )
    if motivo == SENZA_HTTPS:
        return (
            "Le passkey funzionano solo su HTTPS. Fino ad allora si entra con il PIN, "
            "che continua a funzionare."
        )
    if motivo == LIBRERIA_ASSENTE:
        return (
            "Le passkey non sono installate su questo server: manca la libreria "
            "`webauthn`. Si entra con il PIN."
        )
    return ""


def contatore_regredito(salvato: int, nuovo: int) -> bool:
    """Il segnale che una credenziale e' stata copiata.

    L'autenticatore incrementa un contatore a ogni firma. Se ne arriva uno piu'
    basso di quello gia' visto, o la stessa firma e' stata rigiocata o esistono
    due copie della chiave — e una chiave che sta in due posti non e' piu' una
    prova di chi sei.

    Zero da entrambe le parti non e' una regressione: molti autenticatori
    moderni, comprese le passkey sincronizzate fra i dispositivi di una
    persona, non tengono affatto il contatore e mandano sempre zero. Preteso
    li', il controllo non troverebbe cloni: escluderebbe gli utenti normali.
    """
    if nuovo == 0 and salvato == 0:
        return False
    return nuovo <= salvato


def nome_pulito(proposto: str, gia_usati: Optional[frozenset[str]] = None) -> str:
    """Un nome che si legge in un elenco di dispositivi.

    Serve a distinguere «il telefono» da «il portatile» quando se ne revoca
    uno: una passkey senza nome, in un elenco di tre, non si puo' revocare
    con fiducia — e chi non e' sicuro non revoca.
    """
    pulito = re.sub(r"\s+", " ", (proposto or "").strip())[:NOME_MASSIMO]
    if not pulito:
        pulito = NOME_PREDEFINITO

    usati = gia_usati or frozenset()
    if pulito not in usati:
        return pulito

    for numero in range(2, 100):
        tentativo = f"{pulito} ({numero})"
        if tentativo not in usati:
            return tentativo
    return f"{pulito} ({len(usati) + 1})"
