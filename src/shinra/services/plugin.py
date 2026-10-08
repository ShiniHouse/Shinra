# -*- coding: utf-8 -*-
"""I plugin: un manifesto che dice cosa fanno, e permessi che si rispettano (#193).

Oggi aggiungere una capacita' vuol dire modificare il codice di Shinra. Un
plugin e' una cartella in `plugins/` con un **manifesto** (`plugin.json`) e un
modulo (`plugin.py`). Il manifesto dichiara nome, strumenti esposti e permessi;
il modulo li realizza.

**Cosa garantisce questa fase, e cosa no.** I plugin girano **dentro il processo**
di Shinra e sono **codice del proprietario**: caricare codice di terzi dentro il
processo che comanda la casa e' la peggior superficie d'attacco possibile, e non
si fa senza un processo separato (decisione del 2026-10-08, #193). Quindi:

 - un plugin non dichiarato non si carica, e uno non abilitato nemmeno;
 - un permesso non dichiarato non si concede: il plugin agisce sulla casa solo
   tramite il `Contesto`, che controlla ogni richiesta contro il manifesto;
 - serrature, allarme e script **non si possono dichiarare**: il manifesto che
   li chiede non e' valido;
 - un plugin che si rompe (all'avvio o mentre lavora) non ferma il servizio;
 - il registro delle azioni dice quale plugin ha fatto cosa.

Il codice di un plugin potrebbe comunque aggirare il `Contesto` (e' Python nello
stesso processo): i permessi sono un **patto verificabile fra chi scrive e chi
abilita**, non una prigione. Per questo il codice di terzi non si carica.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

from shinra.domain import sensibilita

logger = logging.getLogger("Shinra.Plugin")

NOME_VALIDO = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
CAMPI_MANIFESTO = frozenset({"nome", "versione", "descrizione", "strumenti", "parole", "permessi", "origine"})
CAMPI_PERMESSI = frozenset({"domini_ha", "rete", "conoscenza"})
# Cio' che un plugin non puo' nemmeno chiedere: una serratura aperta dalla
# routine di qualcun altro e' il caso che questa fase esiste per escludere.
DOMINI_NON_DICHIARABILI = sensibilita.DOMINI_SENSIBILI
ORIGINE_PROPRIA = "proprio"


class ManifestoNonValido(Exception):
    """Il manifesto non sta in piedi; `problemi` dice cosa, uno per riga."""

    def __init__(self, problemi: List[str]):
        self.problemi = problemi
        super().__init__("; ".join(problemi))


class PermessoPluginNegato(Exception):
    """Il plugin ha chiesto una cosa che il suo manifesto non dichiara."""


@dataclass(frozen=True)
class Permessi:
    domini_ha: FrozenSet[str] = frozenset()
    rete: FrozenSet[str] = frozenset()
    conoscenza: bool = False

    def descrivi(self) -> str:
        """Cosa chiede, in parole: e' cio' che legge chi decide di abilitarlo."""
        voci: List[str] = []
        if self.domini_ha:
            voci.append("comanda i dispositivi di tipo " + ", ".join(sorted(self.domini_ha)))
        if self.rete:
            voci.append("raggiunge in rete " + ", ".join(sorted(self.rete)))
        if self.conoscenza:
            voci.append("legge la conoscenza della casa")
        return "; ".join(voci) if voci else "nessun permesso: non tocca la casa, la rete ne' la conoscenza"


@dataclass(frozen=True)
class Manifesto:
    nome: str
    versione: str
    descrizione: str
    strumenti: Tuple[str, ...]
    parole: Tuple[str, ...]
    permessi: Permessi
    origine: str = ORIGINE_PROPRIA


def leggi_manifesto(dati: Any) -> Manifesto:
    """Il manifesto validato, o `ManifestoNonValido` con **tutti** i problemi."""
    problemi: List[str] = []
    if not isinstance(dati, dict):
        raise ManifestoNonValido(["il manifesto non e' un oggetto"])

    ignoti = sorted(set(dati) - CAMPI_MANIFESTO)
    if ignoti:
        problemi.append(f"campi sconosciuti: {', '.join(ignoti)}")

    nome = str(dati.get("nome") or "")
    if not NOME_VALIDO.match(nome):
        problemi.append("il nome deve essere minuscolo, lettere, cifre e «_» (2-32 caratteri)")
    for campo in ("versione", "descrizione"):
        if not str(dati.get(campo) or "").strip():
            problemi.append(f"manca «{campo}»")

    strumenti = dati.get("strumenti")
    if not isinstance(strumenti, list) or not strumenti or not all(isinstance(s, str) for s in strumenti):
        problemi.append("«strumenti» deve essere un elenco non vuoto di nomi")
        strumenti = []
    for s in strumenti:
        if not s.startswith(f"{nome}_") or not NOME_VALIDO.match(s):
            problemi.append(
                f"lo strumento «{s}» deve chiamarsi «{nome}_…»: i nomi dei plugin non si confondono"
            )
    if len(set(strumenti)) != len(strumenti):
        problemi.append("ci sono strumenti con lo stesso nome")

    parole = dati.get("parole") or []
    if not isinstance(parole, list) or not all(isinstance(p, str) and p.strip() for p in parole):
        problemi.append("«parole» deve essere un elenco di parole")
        parole = []

    grezzi = dati.get("permessi") or {}
    if not isinstance(grezzi, dict):
        problemi.append("«permessi» deve essere un oggetto")
        grezzi = {}
    ignoti_p = sorted(set(grezzi) - CAMPI_PERMESSI)
    if ignoti_p:
        problemi.append(f"permessi sconosciuti: {', '.join(ignoti_p)}")
    domini = grezzi.get("domini_ha") or []
    rete = grezzi.get("rete") or []
    if not isinstance(domini, list) or not isinstance(rete, list):
        problemi.append("«domini_ha» e «rete» devono essere elenchi")
        domini, rete = [], []
    vietati = sorted(set(map(str, domini)) & DOMINI_NON_DICHIARABILI)
    if vietati:
        problemi.append(f"un plugin non puo' comandare {', '.join(vietati)}: sono cose delicate")
    cattivi = [h for h in rete if not isinstance(h, str) or not h or "/" in h or ":" in h]
    if cattivi:
        problemi.append("«rete» vuole nomi di host semplici (senza «http://», porte o percorsi)")

    if dati.get("origine", ORIGINE_PROPRIA) != ORIGINE_PROPRIA:
        problemi.append("solo i plugin del proprietario (origine «proprio») si caricano in questa fase")

    if problemi:
        raise ManifestoNonValido(problemi)
    return Manifesto(
        nome=nome,
        versione=str(dati["versione"]),
        descrizione=str(dati["descrizione"]),
        strumenti=tuple(strumenti),
        parole=tuple(p.strip().lower() for p in parole),
        permessi=Permessi(
            domini_ha=frozenset(map(str, domini)),
            rete=frozenset(str(h).lower() for h in rete),
            conoscenza=bool(grezzi.get("conoscenza", False)),
        ),
    )


class Contesto:
    """Cio' che un plugin puo' fare sulla casa: ogni richiesta passa dal manifesto."""

    def __init__(self, manifesto: Manifesto):
        self.manifesto = manifesto

    async def comanda(
        self, entity_id: str, servizio: str, dati: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Comanda un dispositivo di un dominio dichiarato (e mai uno delicato)."""
        dominio = entity_id.split(".")[0] if "." in entity_id else ""
        if dominio not in self.manifesto.permessi.domini_ha:
            raise PermessoPluginNegato(
                f"il plugin «{self.manifesto.nome}» non ha dichiarato il permesso di comandare «{dominio or entity_id}»"
            )
        if sensibilita.entita_sensibile(entity_id, servizio):
            raise PermessoPluginNegato(f"«{entity_id}» e' una cosa delicata: un plugin non la comanda")
        from shinra.skills.ha_tools import comanda_dal_motore

        return await comanda_dal_motore(
            {"entity_id": entity_id, "servizio": servizio, "dati": dict(dati or {})}
        )

    async def leggi(self, url: str) -> str:
        """Scarica un indirizzo, ma solo da un host dichiarato."""
        host = (urlparse(url).hostname or "").lower()
        if host not in self.manifesto.permessi.rete:
            raise PermessoPluginNegato(
                f"il plugin «{self.manifesto.nome}» non ha dichiarato il permesso di raggiungere «{host or url}»"
            )
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            risposta = await client.get(url)
            risposta.raise_for_status()
            return risposta.text

    def conoscenza(self) -> List[str]:
        """I fatti della casa, solo se il manifesto lo dichiara."""
        if not self.manifesto.permessi.conoscenza:
            raise PermessoPluginNegato(
                f"il plugin «{self.manifesto.nome}» non ha dichiarato il permesso di leggere la conoscenza"
            )
        from shinra.infra.data_store import data_store

        return [str(f["text"]) for f in data_store.get_knowledge() if f.get("enabled", True)]


@dataclass
class Plugin:
    manifesto: Manifesto
    schemi: Tuple[Dict[str, Any], ...]
    gestori: Dict[str, Callable[..., Any]] = field(default_factory=dict)

    @property
    def agente(self) -> str:
        return f"plugin_{self.manifesto.nome}"


def carica_plugin(cartella: Path) -> Plugin:
    """Carica un plugin da una cartella, o solleva `ManifestoNonValido`.

    Il modulo espone `SCHEMI` (gli schemi degli strumenti, come il catalogo) e
    `GESTORI` (nome -> funzione): ogni funzione riceve il `Contesto` come primo
    argomento e poi gli argomenti del modello. Gli strumenti che il modulo
    espone devono essere **esattamente** quelli del manifesto.
    """
    percorso = cartella / "plugin.json"
    if not percorso.is_file():
        raise ManifestoNonValido(["manca plugin.json"])
    try:
        manifesto = leggi_manifesto(json.loads(percorso.read_text(encoding="utf-8")))
    except json.JSONDecodeError as errore:
        raise ManifestoNonValido([f"plugin.json non e' JSON valido: {errore}"]) from errore
    if manifesto.nome != cartella.name:
        raise ManifestoNonValido(
            [f"il nome «{manifesto.nome}» non e' quello della cartella «{cartella.name}»"]
        )

    modulo = _importa(cartella / "plugin.py", f"shinra_plugin_{manifesto.nome}")
    schemi = tuple(getattr(modulo, "SCHEMI", ()))
    gestori = dict(getattr(modulo, "GESTORI", {}))
    dichiarati = {s["function"]["name"] for s in schemi}
    problemi: List[str] = []
    if dichiarati != set(manifesto.strumenti):
        problemi.append(
            f"gli strumenti del modulo ({', '.join(sorted(dichiarati)) or 'nessuno'}) non sono quelli del "
            f"manifesto ({', '.join(sorted(manifesto.strumenti))})"
        )
    if set(gestori) != set(manifesto.strumenti):
        problemi.append("i gestori del modulo non corrispondono agli strumenti del manifesto")
    if problemi:
        raise ManifestoNonValido(problemi)

    contesto = Contesto(manifesto)
    legati = {nome: _lega(funzione, contesto) for nome, funzione in gestori.items()}
    return Plugin(manifesto=manifesto, schemi=schemi, gestori=legati)


def _lega(funzione: Callable[..., Any], contesto: Contesto) -> Callable[..., Any]:
    """Il gestore col contesto gia' dentro: al registro arriva come ogni altro."""
    import functools
    import inspect

    if inspect.iscoroutinefunction(funzione):

        @functools.wraps(funzione)
        async def con_contesto(**argomenti: Any) -> Any:
            return await funzione(contesto, **argomenti)

        return con_contesto

    @functools.wraps(funzione)
    def sincrono(**argomenti: Any) -> Any:
        return funzione(contesto, **argomenti)

    return sincrono


def _importa(file: Path, nome_modulo: str) -> Any:
    if not file.is_file():
        raise ManifestoNonValido(["manca plugin.py"])
    spec = importlib.util.spec_from_file_location(nome_modulo, file)
    if spec is None or spec.loader is None:
        raise ManifestoNonValido(["plugin.py non si puo' importare"])
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo
    try:
        spec.loader.exec_module(modulo)
    except Exception as errore:
        sys.modules.pop(nome_modulo, None)
        raise ManifestoNonValido([f"plugin.py solleva {type(errore).__name__}: {errore}"]) from errore
    return modulo


# ---------------------------------------------------------------- attivazione

CARICATI: Dict[str, Plugin] = {}
ERRORI: Dict[str, List[str]] = {}


def attiva(cartella: Path, abilitati: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """Carica i plugin abilitati e li mette al lavoro.

    Ritorna `(caricati, errori)`. **Mai solleva**: un plugin non valido finisce
    nell'elenco degli errori e nel log, e gli altri partono. Quelli presenti
    nella cartella ma non abilitati non si importano nemmeno.
    """
    from shinra.services import agenti
    from shinra.skills import registry

    disattiva()
    for nome in abilitati:
        try:
            if not NOME_VALIDO.match(nome):
                raise ManifestoNonValido([f"«{nome}» non e' un nome di plugin valido"])
            plugin = carica_plugin(cartella / nome)
            doppi = sorted(set(plugin.gestori) & set(registry.TOOL_HANDLERS))
            if doppi:
                raise ManifestoNonValido([f"strumenti gia' esistenti: {', '.join(doppi)}"])
        except ManifestoNonValido as e:
            ERRORI[nome] = e.problemi
            logger.error("Plugin «%s» non caricato: %s", nome, "; ".join(e.problemi))
            continue
        CARICATI[nome] = plugin
        registry.TOOL_HANDLERS.update(plugin.gestori)
        registry.PLUGIN_DEGLI_STRUMENTI.update(dict.fromkeys(plugin.gestori, nome))
        agenti.aggiungi_agente(plugin.agente, plugin.schemi, plugin.manifesto.parole)
        # Senza permessi sulla casa non c'e' niente da confermare; con i permessi
        # lo strumento resta «sensibile» (chiuso per difetto) e chiede conferma.
        if not plugin.manifesto.permessi.domini_ha:
            sensibilita.TOOL_SICURI_DINAMICI.update(plugin.manifesto.strumenti)
        logger.info(
            "Plugin «%s» %s caricato: %s",
            nome,
            plugin.manifesto.versione,
            plugin.manifesto.permessi.descrivi(),
        )
    return list(CARICATI), dict(ERRORI)


def disattiva() -> None:
    """Toglie tutti i plugin (si usa prima di ricaricarli, e nei test)."""
    from shinra.services import agenti
    from shinra.skills import registry

    for plugin in CARICATI.values():
        for nome in plugin.gestori:
            registry.TOOL_HANDLERS.pop(nome, None)
            registry.PLUGIN_DEGLI_STRUMENTI.pop(nome, None)
        agenti.togli_agente(plugin.agente)
        sensibilita.TOOL_SICURI_DINAMICI.difference_update(plugin.manifesto.strumenti)
        sys.modules.pop(f"shinra_plugin_{plugin.manifesto.nome}", None)
    CARICATI.clear()
    ERRORI.clear()
