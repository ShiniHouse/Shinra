"""Cosa avvisare, a chi, su quale canale, e cosa non si puo' zittire.

Fino a qui la casa aveva un canale solo — l'annuncio sull'Echo — e un evento
che non lo trovava restava muto. `casa.intrusione` era esattamente questo: lo
scriveva `services/allarme.py` e non lo ascoltava nessuno, nemmeno la
dashboard aperta. Un allarme che scatta mentre nessuno guarda non ha avvisato
nessuno.

Le due decisioni che questo modulo tiene ferme:

**La priorita' non e' un'etichetta, e' un permesso.** Un'intrusione suona
anche se la persona ha silenziato tutto, un avviso energetico no. Se il
silenzioso potesse spegnere un allarme, il silenzioso sarebbe un modo per
spegnere l'allarme dimenticandosene.

**Il canale sbagliato e' peggio del canale mancante.** Un'intrusione annunciata
ad alta voce in casa avvisa il ladro che ci sono sensori, non avvisa chi e'
fuori: l'urgenza va dove sta la persona, e se e' fuori il telefono e' l'unico
posto giusto.

Qui non si manda niente: entrano un evento e le preferenze, esce l'elenco di
chi va avvisato e come.

Riferimento: issue #29.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlparse

# I canali. `web` e' la dashboard aperta, `push` il telefono anche a
# applicazione chiusa, `voce` l'annuncio su un Echo in casa.
WEB = "web"
PUSH = "push"
VOCE = "voce"
# Un server `ntfy` **in casa** (#389): solo in uscita, e solo per chi lo chiede.
NTFY = "ntfy"

CANALI = (WEB, PUSH, VOCE, NTFY)
# I canali spenti finche' la persona non li accende: tutti gli altri nascono accesi.
CANALI_SU_RICHIESTA = frozenset({NTFY})

# Le priorita', dalla piu' bassa. Non sono un'etichetta: decidono chi puo'
# essere zittito.
INFORMATIVA = "informativa"
IMPORTANTE = "importante"
URGENTE = "urgente"

PRIORITA = (INFORMATIVA, IMPORTANTE, URGENTE)
_PESO = {INFORMATIVA: 0, IMPORTANTE: 1, URGENTE: 2}

# Le categorie che una persona puo' silenziare separatamente. «Silenzia gli
# avvisi sui consumi» non deve silenziare l'allarme.
PROMEMORIA = "promemoria"
TIMER = "timer"
SICUREZZA = "sicurezza"
PRESENZA = "presenza"
ENERGIA = "energia"
MANUTENZIONE = "manutenzione"
# Un lavoro lungo che Shinra ha finito («ci penso»): l'avviso dice solo che e' pronto, mai il contenuto.
LAVORO = "lavoro"

CATEGORIE = (PROMEMORIA, TIMER, SICUREZZA, PRESENZA, ENERGIA, MANUTENZIONE, LAVORO)

# Le categorie che il silenzioso non puo' spegnere. E' un elenco corto
# apposta: piu' cose ci si mettono, meno significa il silenzioso, e una
# persona che non riesce a far tacere la casa la spegne del tutto.
NON_SILENZIABILI = frozenset({SICUREZZA})


@dataclass(frozen=True)
class Avviso:
    """Cosa dire, quanto e' urgente, e dove porta se lo si tocca."""

    categoria: str
    titolo: str
    testo: str = ""
    priorita: str = INFORMATIVA
    # Dove aprire l'applicazione quando si tocca la notifica. Una notifica
    # che apre la schermata iniziale costringe a cercare cio' che e'
    # appena successo.
    destinazione: str = "/"
    dati: Mapping[str, Any] = field(default_factory=dict)

    @property
    def urgente(self) -> bool:
        return self.priorita == URGENTE

    @property
    def silenziabile(self) -> bool:
        return self.categoria not in NON_SILENZIABILI


@dataclass(frozen=True)
class Preferenze:
    """Cosa una persona vuole ricevere, e dove.

    Il valore predefinito e' «tutto, su tutti i canali»: una casa che di
    serie non avvisa e' una casa che sembra rotta, e chi non vuole essere
    disturbato lo dice.
    """

    utente: str
    canali: Mapping[str, bool] = field(default_factory=dict)
    categorie_silenziate: frozenset[str] = frozenset()
    silenzioso: bool = False

    def vuole_canale(self, canale: str) -> bool:
        return bool(self.canali.get(canale, canale not in CANALI_SU_RICHIESTA))

    def vuole_categoria(self, categoria: str) -> bool:
        return categoria not in self.categorie_silenziate


def canali_per(avviso: Avviso, preferenze: Optional[Preferenze] = None) -> list[str]:
    """Su quali canali va questo avviso, per questa persona.

    L'ordine e' quello di consegna, e non e' casuale: prima la dashboard, che
    costa niente e arriva subito a chi sta guardando; poi il telefono; per
    ultima la voce, che e' la piu' invadente e l'unica che disturba anche chi
    non era il destinatario.
    """
    if preferenze is None:
        return [WEB, PUSH] if avviso.urgente else [WEB]

    if not preferenze.vuole_categoria(avviso.categoria) and avviso.silenziabile:
        return []

    if preferenze.silenzioso and avviso.silenziabile:
        # Il silenzioso lascia passare la dashboard: chi sta guardando lo
        # schermo non viene disturbato da cio' che c'e' gia' scritto sopra.
        return [WEB] if preferenze.vuole_canale(WEB) else []

    scelti = [c for c in (WEB, PUSH, NTFY) if preferenze.vuole_canale(c)]

    # La voce solo per le cose urgenti, e mai per la sicurezza: un allarme
    # annunciato ad alta voce avvisa chi e' in casa — cioe' eventualmente il
    # ladro — e non avvisa chi e' fuori.
    if avviso.urgente and avviso.categoria != SICUREZZA and preferenze.vuole_canale(VOCE):
        scelti.append(VOCE)

    return scelti


def almeno(priorita: str, soglia: str) -> bool:
    return _PESO.get(priorita, 0) >= _PESO.get(soglia, 0)


def preferenze_da_righe(utente: str, righe: Iterable[Mapping[str, Any]]) -> Preferenze:
    """Dalle righe del database alle preferenze di una persona."""
    canali: dict[str, bool] = {}
    silenziate: set[str] = set()
    silenzioso = False

    for riga in righe:
        if str(riga.get("user_id")) != utente:
            continue
        chiave = str(riga.get("chiave") or "")
        valore = bool(riga.get("valore"))
        if chiave == "silenzioso":
            silenzioso = valore
        elif chiave.startswith("canale."):
            canali[chiave.split(".", 1)[1]] = valore
        elif chiave.startswith("categoria.") and not valore:
            silenziate.add(chiave.split(".", 1)[1])

    return Preferenze(utente, canali, frozenset(silenziate), silenzioso)


# ------------------------------------------------------------------ ntfy in casa (#389)

_SUFFISSI_LOCALI = (".local", ".lan", ".home", ".internal", ".localdomain", ".home.arpa")


def indirizzo_locale(url: str) -> bool:
    """Se l'indirizzo di un server ntfy sta **in casa**: loopback, rete privata, un nome della rete locale.

    Il punto di ntfy e' non passare da terzi: un indirizzo pubblico (`ntfy.sh`, un VPS) lo tradirebbe, e per questo non si
    usa. Un nome senza punti (`ntfy`, il servizio di un container accanto) e' locale; un nome che finisce in `.local`,
    `.lan`, `.home` o simili anche. Il resto no. Vale per `http` e `https`.
    """
    try:
        analizzato = urlparse((url or "").strip())
        host = (analizzato.hostname or "").lower()
    except ValueError:
        return False
    if analizzato.scheme not in ("http", "https") or not host:
        return False
    try:
        indirizzo = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host or host.endswith(_SUFFISSI_LOCALI)
    return indirizzo.is_loopback or indirizzo.is_private or indirizzo.is_link_local


def argomento_ntfy(segreto: str, utente: str) -> str:
    """L'argomento su cui questa persona ascolta: stabile, e impossibile da indovinare senza il segreto del server.

    Su un ntfy senza account l'argomento *e'* la chiave: chi lo conosce legge gli avvisi. Per questo non e' il nome della
    persona ma un'impronta con il segreto di Shinra, e non si conserva da nessuna parte: si ricalcola.
    """
    impronta = hmac.new(segreto.encode(), f"ntfy:{utente}".encode(), hashlib.sha256).hexdigest()
    return f"shinra-{impronta[:20]}"
