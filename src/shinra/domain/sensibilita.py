"""Quali azioni non si fanno sulla parola del modello (issue #192).

Un principio permanente di Shinra: **il modello non e' fidato.** Sceglie gli
strumenti da solo, sulla base di una frase che puo' aver capito male — o che
qualcuno gli ha fatto dire apposta. Per accendere una luce va bene. Per aprire
una porta di casa no.

Questo modulo decide, per ogni azione, in quale di tre classi cade:

 - **sicura**: parte e basta;
 - **sensibile**: serrature, allarme, garage e porte, e gli script — cioe' tutto
   cio' che, sbagliato, lascia entrare qualcuno o spegne una difesa. Non parte
   finche' una persona non l'ha confermata, e solo quella persona;
 - **vietata agli agenti**: non parte mai da un agente, nemmeno confermata
   (gestire utenti, PIN, permessi, esportare dati). Oggi nessuno strumento lo e':
   l'elenco c'e' perche' un test lo faccia rispettare il giorno che qualcuno
   ne scrive uno.

**Chiuso per difetto.** Uno strumento che questo modulo non conosce e' sensibile.
Aggiungere uno strumento al registro senza dire cos'e' non lo rende pericoloso:
lo rende scomodo, e un test lo segnala. Il contrario — considerarlo sicuro finche'
qualcuno non se ne accorge — e' il modo in cui una serratura finisce dietro a uno
strumento nuovo senza che nessuno l'abbia deciso.

Il modulo e' puro: niente rete, niente database. Chi sa risolvere un alias in un
`entity_id` lo passa (`risolvi`).

Riferimento: issue #192, ADR 0004.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping, Optional

SICURA = "sicura"
SENSIBILE = "sensibile"
VIETATA = "vietata"

# Gli strumenti che non toccano niente di delicato, qualunque argomento ricevano.
TOOL_SICURI = frozenset(
    {
        "get_weather",
        "search_wikipedia",
        "search_web",
        "get_latest_news",
        "get_home_status",
        "get_indoor_temperature",
        "add_reminder",
        "list_reminders",
        "delete_reminder",
        "comanda_media",
        "comanda_aspirapolvere",
        "comanda_ventilatore",
        "stato_aperture",
        "comanda_simulazione",
        "comanda_clima",
        "stato_clima",
        "stato_tapparella",
        "fascia_corrente",
        "consumo_energia",
        "costo_dispositivo",
        "aggiungi_a_lista",
        "leggi_lista",
        "togli_da_lista",
        "quali_liste",
        "impegni",
        "prossimi_impegni",
        "aggiungi_impegno",
        "aggiungi_scadenza",
        "scadenze_in_arrivo",
        "segna_fatta",
        "dimentica_scadenza",
        # Una modalita' e' una sequenza di passi scritta da una persona: il
        # suo effetto su una serratura lo ferma `servizio_sensibile`, in fondo,
        # dove si chiama Home Assistant.
        "activate_mode",
    }
)

# Gli strumenti dei plugin che non hanno nessun permesso sulla casa (#193): li aggiunge
# `services/plugin` quando li carica e li toglie quando li scarica. Un plugin che comanda
# dispositivi non c'e' qui: resta «sensibile», chiuso per difetto, e chiede conferma.
TOOL_SICURI_DINAMICI: set[str] = set()

# Sicuri **o no, a seconda degli argomenti**: li decide `classifica`.
TOOL_CONDIZIONATI = frozenset(
    {
        "control_device",
        "comanda_serratura",
        "comanda_allarme",
        "comanda_tapparella",
        "activate_scene_or_routine",
    }
)

# Non devono esistere come strumenti del modello. Se un giorno qualcuno ne
# scrive uno con questo nome, `test_sensibilita` fallisce.
TOOL_VIETATI_AGLI_AGENTI = frozenset(
    {
        "gestisci_utenti",
        "crea_utente",
        "elimina_utente",
        "cambia_pin",
        "modifica_permessi",
        "esporta_dati",
        "elimina_dati",
        "cancella_registro",
    }
)

DOMINI_SENSIBILI = frozenset({"lock", "alarm_control_panel", "script"})

# Parole che, in un nome o in un `entity_id` di tapparella o interruttore, dicono
# «questa e' un'apertura verso l'esterno».
_APERTURE = re.compile(r"(garage|portone|cancell|basculante|\bporta\b|\bdoor\b|\bgate\b)", re.IGNORECASE)
_SERRATURE_E_ALLARMI = re.compile(r"(serratur|lucchett|allarm|\balarm|\block\b)", re.IGNORECASE)


def _parole(entita: str) -> str:
    """`cover.porta_garage` -> `cover porta garage`: i confini di parola devono funzionare."""
    return re.sub(r"[._]+", " ", entita)


_AZIONI_INNOCUE = frozenset(
    {"chiudi", "close", "ferma", "stop", "stato", "blocca", "lock", "arma_casa", "arma_fuori"}
)


def _dominio(entita: str) -> str:
    return entita.split(".", 1)[0] if "." in entita else ""


def _e_apertura(entita: str) -> bool:
    return bool(_APERTURE.search(_parole(entita)))


def entita_sensibile(entita: str, azione: str = "") -> bool:
    """Se comandare questa entita' in questo modo va confermato.

    `azione` vuota vuol dire «non lo so»: nel dubbio, si conferma.
    """
    entita = (entita or "").strip()
    if not entita:
        return False
    azione = (azione or "").strip().lower()
    dominio = _dominio(entita)
    if dominio in DOMINI_SENSIBILI:
        # Su una serratura, chiudere o chiedere lo stato non apre niente. Su uno
        # script non c'e' modo di saperlo: parte quello che c'e' scritto dentro.
        return dominio == "script" or azione not in _AZIONI_INNOCUE
    if dominio == "cover" or not dominio:
        if _SERRATURE_E_ALLARMI.search(_parole(entita)):
            return azione not in _AZIONI_INNOCUE
        if _e_apertura(entita):
            return azione not in _AZIONI_INNOCUE
    return False


def classifica(
    tool: str,
    argomenti: Optional[Mapping[str, Any]] = None,
    risolvi: Callable[[str], Optional[str]] = lambda nome: None,
) -> str:
    """La classe di un'azione: `SICURA`, `SENSIBILE` o `VIETATA`."""
    argomenti = argomenti or {}
    if tool in TOOL_VIETATI_AGLI_AGENTI:
        return VIETATA
    if tool in TOOL_SICURI or tool in TOOL_SICURI_DINAMICI:
        return SICURA
    if tool not in TOOL_CONDIZIONATI:
        return SENSIBILE  # chiuso per difetto: uno strumento che non conosco non e' sicuro

    # Il bersaglio puo' essere un `entity_id` o un nome naturale («serratura ingresso»):
    # il modello puo' scrivere l'uno o l'altro, e il controllo deve valere per tutti e due.
    bersaglio = str(argomenti.get("entity_id") or "").strip()
    if bersaglio and "." not in bersaglio:
        bersaglio = risolvi(bersaglio) or bersaglio

    azione = str(argomenti.get("azione") or argomenti.get("action") or "").strip().lower()
    if tool == "comanda_serratura":
        # Chiudere e chiedere lo stato non aprono niente; ogni altra cosa, o nessuna azione, si'.
        return SICURA if azione in {"blocca", "chiudi", "lock", "stato"} else SENSIBILE
    if tool == "comanda_allarme":
        return SICURA if azione in {"arma_casa", "arma_fuori", "arma_in_casa", "arma", "stato"} else SENSIBILE
    if tool == "activate_scene_or_routine":
        return SENSIBILE if entita_sensibile(bersaglio, "attiva") else SICURA
    # control_device (`action`) e comanda_tapparella (`azione`).
    return SENSIBILE if entita_sensibile(bersaglio, azione) else SICURA


def bersaglio_di(argomenti: Optional[Mapping[str, Any]]) -> str:
    """Il bersaglio, come si scrive nel registro e nella domanda di conferma."""
    return str((argomenti or {}).get("entity_id") or "").strip()


# ---------------------------------------------------------------- in fondo

_ARMAMENTI = frozenset({"alarm_arm_home", "alarm_arm_away", "alarm_arm_night", "lock"})


def _entita_di(dati: Mapping[str, Any]) -> Iterable[str]:
    valore = dati.get("entity_id")
    if isinstance(valore, str):
        yield from (v.strip() for v in valore.split(",") if v.strip())
    elif isinstance(valore, (list, tuple)):
        yield from (str(v).strip() for v in valore)


def servizio_sensibile(dominio: str, servizio: str, dati: Optional[Mapping[str, Any]] = None) -> bool:
    """Se questa chiamata a Home Assistant apre o disarma qualcosa.

    E' la rete di sicurezza in fondo al percorso, quella che vale anche per cio'
    che dentro non si vede: una modalita' con un passo «sblocca la porta» scritto
    da una persona, ma attivata dal modello, passa di qui. Qui non c'e' modo di
    chiedere conferma — e' una chiamata, non una conversazione — quindi si ferma.
    """
    dati = dati or {}
    entita = list(_entita_di(dati))
    if dominio == "lock":
        return servizio != "lock"
    if dominio == "alarm_control_panel":
        return servizio not in _ARMAMENTI
    if dominio == "script":
        return True
    for e in entita:
        d = _dominio(e)
        if d == "lock" and servizio != "lock":
            return True
        if d == "alarm_control_panel" and servizio not in _ARMAMENTI:
            return True
        if d == "script":
            return True
        if (
            d == "cover"
            and _e_apertura(e)
            and servizio not in {"close_cover", "stop_cover", "close_cover_tilt"}
        ):
            return True
    return False
