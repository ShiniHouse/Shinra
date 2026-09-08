"""Le frecce vanno in una direzione sola, e quelle che non ci vanno sono contate.

`docs/ARCHITECTURE.md` dichiara le regole di dipendenza fra i livelli. Fino
allo spostamento sotto `src/shinra/` erano una dichiarazione di intenti: il
codice stava in cartelle di primo livello, nulla impediva a un tool di
importare un router, e nessuno se ne sarebbe accorto.

Adesso i livelli sono cartelle, quindi la regola si puo' verificare. Ma
verificarla e basta avrebbe reso la suite rossa da subito: le violazioni
esistono, sono diciannove, e ripararle tutte dentro allo spostamento
avrebbe prodotto una modifica che nessuno puo' rileggere.

Quindi questo test non chiede che siano zero: chiede che siano **esattamente
queste**. Una violazione nuova fa fallire la suite; una riparata la fa
fallire anche lei, e la si toglie da qui — cosi' il debito e' scritto, si
vede quanto e', e si accorcia una riga alla volta invece di restare una nota
in fondo a un documento.

Riferimento: issue #16, docs/ARCHITECTURE.md §3.
"""

from __future__ import annotations

import ast
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
SORGENTI = RADICE / "src" / "shinra"

LIVELLI = ("config", "domain", "infra", "services", "skills", "channels", "api")

# Chi puo' importare chi. Un livello puo' sempre importare se stesso.
#
# `radice` sono i moduli che stanno direttamente sotto `shinra/` — percorsi,
# versione: non dipendono da niente e li usano tutti. `avvio` e' il punto di
# ingresso, che per mestiere mette insieme tutto il resto.
CONSENTITO: dict[str, set[str]] = {
    "radice": set(),
    "config": {"radice"},
    "domain": {"radice"},
    "infra": {"radice", "config", "domain"},
    # Le capacita' (accendi la luce, che tempo fa) stanno sopra
    # l'infrastruttura e sotto chi le orchestra.
    "skills": {"radice", "config", "domain", "infra"},
    "services": {"radice", "config", "domain", "infra", "skills"},
    "channels": {"radice", "config", "domain", "services", "skills"},
    "api": {"radice", "config", "domain", "services", "skills", "channels"},
    "avvio": set(LIVELLI) | {"radice"},
}

# Il debito, riga per riga. Ogni voce e' «file -> modulo importato».
#
# Non e' un elenco di eccezioni tollerate: e' la lista di cio' che resta da
# fare, tenuta dove fallisce se qualcuno la allunga. I raggruppamenti dicono
# perche' ciascuna esiste, perche' una voce senza motivo diventa permanente.
DEBITO: frozenset[str] = frozenset(
    {
        # `api` costruisce a mano gli oggetti di infrastruttura all'avvio e
        # nel pannello di amministrazione. Andranno dietro a un servizio: e'
        # il gruppo piu' numeroso e quello che vale la pena sciogliere per
        # primo.
        "api/app.py -> shinra.infra.data_store",
        "api/app.py -> shinra.infra.db",
        "api/app.py -> shinra.infra.homeassistant.client",
        "api/app.py -> shinra.infra.llm.ollama",
        "api/app.py -> shinra.infra.scheduler.motore",
        "api/app.py -> shinra.infra.tts",
        "api/routes_admin.py -> shinra.infra.data_store",
        "api/routes_admin.py -> shinra.infra.db",
        "api/routes_admin.py -> shinra.infra.homeassistant.client",
        "api/routes_admin.py -> shinra.infra.llm.ollama",
        # I dispositivi fidati fanno SQLAlchemy direttamente dentro il
        # livello delle rotte: e' un servizio travestito da modulo dell'API.
        "api/dispositivi.py -> shinra.infra.db.modelli",
        "api/dispositivi.py -> shinra.infra.db.motore",
        # La skill Alexa sintetizza la voce da se'.
        "channels/alexa/skill_handler.py -> shinra.infra.tts",
        # `prompt_templates` usa `UserProfile`, che oggi vive dentro il
        # servizio degli utenti. Il modello del profilo e' materia di
        # `domain/`: e' lo spostamento che scioglie questa e apre la strada
        # a un `domain/` che contenga qualcosa.
        "config/prompt_templates.py -> shinra.services.user_manager",
        # Il controllo dei permessi sta nel client di Home Assistant perche'
        # e' li' che passa tutto — comandi diretti, scenari, routine. E' una
        # scelta voluta (ADR 0004) e la freccia all'indietro e' il suo
        # prezzo: si toglie invertendo la dipendenza, non spostando il
        # controllo.
        "infra/homeassistant/client.py -> shinra.services.permessi",
        "infra/scheduler/motore.py -> shinra.services.timer_engine",
        # Il registro dei tool non dovrebbe conoscere i permessi: il
        # controllo e' gia' al passaggio obbligato del client.
        "services/user_manager.py -> shinra.api.sicurezza",
        "skills/registry.py -> shinra.services",
        "skills/registry.py -> shinra.services.permessi",
    }
)


def _livello(modulo: str) -> str:
    parti = modulo.split(".")
    if modulo == "shinra" or len(parti) < 2:
        return "radice"
    if parti[1] == "avvio":
        return "avvio"
    return parti[1] if parti[1] in LIVELLI else "radice"


def _importati(file: Path) -> list[str]:
    albero = ast.parse(file.read_text(encoding="utf-8"))
    nomi: list[str] = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nomi.append(nodo.module)
        elif isinstance(nodo, ast.Import):
            nomi.extend(alias.name for alias in nodo.names)
    return [n for n in nomi if n == "shinra" or n.startswith("shinra.")]


def violazioni() -> set[str]:
    trovate: set[str] = set()
    for file in sorted(SORGENTI.rglob("*.py")):
        modulo = ".".join(file.relative_to(SORGENTI.parent).with_suffix("").parts)
        modulo = modulo.removesuffix(".__init__")
        mio = _livello(modulo)
        for importato in _importati(file):
            suo = _livello(importato)
            if suo != mio and suo not in CONSENTITO[mio]:
                trovate.add(f"{file.relative_to(SORGENTI).as_posix()} -> {importato}")
    return trovate


def test_il_pacchetto_ha_i_livelli_dichiarati():
    """Se una cartella sparisce o cambia nome, il resto di questo file
    smette di guardare e nessuno se ne accorge."""
    presenti = {p.name for p in SORGENTI.iterdir() if p.is_dir() and not p.name.startswith("__")}

    assert set(LIVELLI) <= presenti, f"livelli mancanti: {set(LIVELLI) - presenti}"


def test_nessuna_dipendenza_nuova_fra_livelli():
    nuove = sorted(violazioni() - DEBITO)

    assert nuove == [], (
        "queste dipendenze violano le regole di docs/ARCHITECTURE.md §3 e non "
        f"erano nel debito noto: {nuove}"
    )


def test_il_debito_dichiarato_esiste_ancora():
    """L'altra meta' del cricchetto.

    Una voce riparata deve sparire da `DEBITO`, altrimenti l'elenco diventa
    un cimitero e fra sei mesi nessuno sa piu' quali righe descrivano un
    problema vero.
    """
    sparite = sorted(DEBITO - violazioni())

    assert sparite == [], (
        "queste violazioni non ci sono piu': toglile da DEBITO, cosi' il "
        f"cricchetto resta stretto — {sparite}"
    )
