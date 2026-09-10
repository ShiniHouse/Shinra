"""Il grafo di una routine: cosa viene dopo cosa, e cosa non torna.

L'editor a nodi e' il pezzo piu' bello del progetto e finora eseguiva la cosa
piu' semplice: una visita in ampiezza che percorre **tutti** gli archi. Con
quattro tipi di nodo — innesco, dispositivo, ritardo, annuncio — bastava,
perche' non c'era niente da decidere: il flusso era sempre lineare.

Con un nodo condizione non basta piu'. Una condizione ha due uscite e se ne
percorre **una**, e una visita che le percorre entrambe non e' una condizione:
e' una decorazione che non decide niente. E' il motivo per cui questo modulo
esiste.

**Le condizioni sono quelle della issue #27**, non un vocabolario nuovo:
`regole.motivo_condizione` risponde alla stessa domanda per il motore di
regole e per un nodo del grafo. Due implementazioni divergerebbero, e la
divergenza si vedrebbe come «la stessa condizione si comporta in modo diverso
a seconda di dove l'hai scritta».

Qui non si esegue niente: si dice cosa eseguire. Chiamare Home Assistant, o
aspettare, spetta a chi sta sopra — ed e' cio' che rende questa parte
verificabile senza una casa.

Riferimento: issue #28, ADR 0003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from shinra.domain import regole

# --------------------------------------------------------------------------
# I tipi di nodo
# --------------------------------------------------------------------------
#
# I primi quattro esistevano gia' e i loro nomi non si toccano: sono scritti
# nelle routine salvate di chi usa Shinra da prima, e rinominarli vorrebbe
# dire migrare i dati di casa per un'esigenza di stile.

TRIGGER = "trigger"
DISPOSITIVO = "ha_device"
SERVIZIO = "ha_service"
RITARDO = "delay"
ANNUNCIO = "tts"

# Nuovi con la issue #28.
CONDIZIONE = "condizione"
NOTIFICA = "notifica"

AZIONI = (DISPOSITIVO, SERVIZIO, RITARDO, ANNUNCIO, NOTIFICA)
TIPI = (TRIGGER, CONDIZIONE, *AZIONI)

# I due rami di una condizione. Sono etichette sugli **archi**, non sui nodi:
# e' l'arco a sapere se parte dall'uscita «vero» o da quella «falso», ed e'
# l'unica informazione che serve per percorrerne uno solo.
VERO = "vero"
FALSO = "falso"
RAMI = (VERO, FALSO)

# --------------------------------------------------------------------------
# I problemi che un grafo puo' avere
# --------------------------------------------------------------------------

NODO_SCOLLEGATO = "nodo_scollegato"
CICLO = "ciclo"
RAMO_SENZA_USCITA = "ramo_senza_uscita"
SENZA_INIZIO = "senza_inizio"
ARCO_ROTTO = "arco_rotto"
TIPO_SCONOSCIUTO = "tipo_sconosciuto"


@dataclass(frozen=True)
class Problema:
    """Cosa non va, e **dove**.

    `nodi` porta gli identificativi coinvolti perche' l'editor possa
    illuminarli: «il grafo non e' valido» manda a guardarli tutti, e chi ha
    disegnato trenta nodi non lo fa — salva lo stesso, o rinuncia.
    """

    tipo: str
    messaggio: str
    nodi: tuple[str, ...] = ()


@dataclass(frozen=True)
class Passo:
    """Un nodo da eseguire, con quello che serve per eseguirlo."""

    id: str
    tipo: str
    dati: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Il grafo
# --------------------------------------------------------------------------


class Grafo:
    """Nodi e archi, con le domande che ci si fa sopra.

    Non e' un dizionario perche' le due domande utili — «da dove si comincia»
    e «cosa viene dopo questo, per questo ramo» — richiedono le adiacenze
    costruite una volta sola, e ricostruirle a ogni passo su una routine di
    trenta nodi e' il genere di cosa che nessuno nota finche' non e' lenta.
    """

    def __init__(self, nodi: Sequence[Mapping[str, Any]], archi: Sequence[Mapping[str, Any]]) -> None:
        self.nodi = [n for n in nodi if n.get("id")]
        self.archi = list(archi or ())
        self.mappa: dict[str, Mapping[str, Any]] = {str(n["id"]): n for n in self.nodi}

        # Adiacenze per ramo. `None` e' il ramo di un arco senza etichetta,
        # cioe' quasi tutti: solo le uscite di una condizione ne portano una.
        self._uscite: dict[str, list[tuple[Optional[str], str]]] = {}
        self._entranti: dict[str, int] = dict.fromkeys(self.mappa, 0)

        for arco in self.archi:
            partenza = str(arco.get("from") or "")
            arrivo = str(arco.get("to") or "")
            if partenza not in self.mappa or arrivo not in self.mappa:
                continue
            ramo = arco.get("ramo") or arco.get("branch")
            self._uscite.setdefault(partenza, []).append((str(ramo).lower() if ramo else None, arrivo))
            self._entranti[arrivo] = self._entranti.get(arrivo, 0) + 1

    # ------------------------------------------------------------ lettura

    def tipo_di(self, nodo_id: str) -> str:
        return str((self.mappa.get(nodo_id) or {}).get("type") or "")

    def dati_di(self, nodo_id: str) -> Mapping[str, Any]:
        return (self.mappa.get(nodo_id) or {}).get("data") or {}

    def inizi(self) -> list[str]:
        """Da dove parte l'esecuzione.

        Prima i nodi trigger; se non ce ne sono, quelli senza archi entranti.
        E' la regola che c'era gia' dentro il tool, e resta perche' le routine
        salvate ci contano: alcune non hanno un nodo trigger e cominciano dal
        primo nodo disegnato.
        """
        senza_entranti = [i for i in self.mappa if self._entranti.get(i, 0) == 0]

        triggers = [i for i in senza_entranti if self.tipo_di(i) == TRIGGER]
        if triggers:
            return triggers
        if senza_entranti:
            return senza_entranti
        return [str(self.nodi[0]["id"])] if self.nodi else []

    def successivi(self, nodo_id: str, ramo: Optional[str] = None) -> list[str]:
        """Cosa viene dopo questo nodo.

        Con `ramo` valorizzato si percorrono **solo** gli archi di quel ramo,
        piu' quelli senza etichetta: un arco senza etichetta che esce da una
        condizione e' un disegno vecchio o un errore, e interromperlo
        silenziosamente romperebbe routine che oggi funzionano.
        """
        uscite = self._uscite.get(nodo_id, [])
        if ramo is None:
            return [arrivo for _, arrivo in uscite]
        return [arrivo for etichetta, arrivo in uscite if etichetta in (ramo, None)]

    def rami_disponibili(self, nodo_id: str) -> set[str]:
        return {e for e, _ in self._uscite.get(nodo_id, []) if e}


# --------------------------------------------------------------------------
# La validazione
# --------------------------------------------------------------------------


def valida(nodi: Sequence[Mapping[str, Any]], archi: Sequence[Mapping[str, Any]]) -> list[Problema]:
    """Tutto cio' che non va, non solo il primo.

    Restituire il primo problema costringe a salvare, leggere, correggere e
    risalvare una volta per errore: chi ha disegnato un grafo sbagliato in tre
    punti vuole saperlo una volta sola.

    Un grafo **vuoto** non e' un errore: e' una routine appena creata, e
    rifiutare di salvarla vorrebbe dire non poterla cominciare.
    """
    problemi: list[Problema] = []
    if not nodi:
        return problemi

    grafo = Grafo(nodi, archi)
    conosciuti = set(grafo.mappa)

    # 1. Archi che puntano al vuoto. Vengono prima perche' tutto il resto si
    #    calcola sulle adiacenze, e un arco rotto le falsa.
    rotti = [
        f"{a.get('from')}→{a.get('to')}"
        for a in grafo.archi
        if str(a.get("from") or "") not in conosciuti or str(a.get("to") or "") not in conosciuti
    ]
    if rotti:
        problemi.append(
            Problema(
                ARCO_ROTTO,
                f"Ci sono collegamenti verso nodi che non esistono: {', '.join(rotti)}.",
            )
        )

    # 2. Tipi che l'esecutore non sa eseguire. Un nodo cosi' non da' errore:
    #    viene saltato in silenzio, e chi l'ha disegnato crede che funzioni.
    sconosciuti = tuple(i for i in grafo.mappa if grafo.tipo_di(i) not in TIPI)
    if sconosciuti:
        problemi.append(
            Problema(
                TIPO_SCONOSCIUTO,
                "Alcuni nodi hanno un tipo che non so eseguire: verrebbero saltati in silenzio.",
                sconosciuti,
            )
        )

    # 3. Nodi che nessuno raggiunge. Non e' un dettaglio estetico: e' lavoro
    #    disegnato che non verra' mai fatto, e non si vede guardando il grafo.
    raggiunti = _raggiungibili(grafo)
    scollegati = tuple(sorted(set(grafo.mappa) - raggiunti))
    if scollegati:
        problemi.append(
            Problema(
                NODO_SCOLLEGATO,
                "Questi nodi non sono collegati a niente che venga eseguito: " "resterebbero fermi.",
                scollegati,
            )
        )

    # 4. Cicli.
    anello = _trova_ciclo(grafo)
    if anello:
        problemi.append(
            Problema(
                CICLO,
                "Questi nodi si rimandano a vicenda: l'esecuzione non finirebbe mai. "
                f"L'anello e' {' → '.join(anello)}.",
                tuple(anello),
            )
        )

    # 5. Condizioni con un ramo solo. Una condizione a cui manca l'uscita
    #    «falso» non e' una condizione: e' un filtro che a volte ferma tutto,
    #    e chi l'ha disegnata si aspetta due strade.
    monche = tuple(
        i
        for i in grafo.mappa
        if grafo.tipo_di(i) == CONDIZIONE and len(grafo.rami_disponibili(i)) < len(RAMI)
    )
    if monche:
        problemi.append(
            Problema(
                RAMO_SENZA_USCITA,
                "Queste condizioni hanno una sola uscita collegata: l'altro ramo "
                "non porterebbe da nessuna parte.",
                monche,
            )
        )

    # 6. Nessun punto di partenza: succede solo se ogni nodo ha un arco
    #    entrante, cioe' se il grafo e' tutto un anello.
    if not [i for i in grafo.mappa if grafo._entranti.get(i, 0) == 0]:
        problemi.append(
            Problema(SENZA_INIZIO, "Nessun nodo puo' iniziare la routine: tutti hanno un ingresso.")
        )

    return problemi


def _raggiungibili(grafo: Grafo) -> set[str]:
    """Cosa si tocca partendo dagli inizi, percorrendo **tutti** i rami.

    Qui i rami si percorrono entrambi di proposito: la domanda non e' «cosa
    verra' eseguito stavolta» ma «cosa potrebbe esserlo». Un nodo raggiungibile
    solo dal ramo falso e' collegato, anche se stasera non ci si passa.
    """
    visti: set[str] = set()
    coda = list(grafo.inizi())
    while coda:
        corrente = coda.pop(0)
        if corrente in visti:
            continue
        visti.add(corrente)
        coda.extend(grafo.successivi(corrente))
    return visti


def _trova_ciclo(grafo: Grafo) -> list[str]:
    """L'anello, se c'e', con i nodi che lo compongono.

    Restituisce i nodi e non un booleano per la stessa ragione per cui
    `regole.verifica_catena` porta con se' la catena: «c'e' un ciclo» manda a
    guardare tutto il disegno, «A → B → A» dice dove tagliare.
    """
    BIANCO, GRIGIO, NERO = 0, 1, 2
    colore = dict.fromkeys(grafo.mappa, BIANCO)
    percorso: list[str] = []

    def scendi(nodo: str) -> list[str]:
        colore[nodo] = GRIGIO
        percorso.append(nodo)
        for prossimo in grafo.successivi(nodo):
            if colore.get(prossimo) == GRIGIO:
                # L'anello va dal primo incontro fino a qui, piu' la chiusura.
                inizio = percorso.index(prossimo)
                return [*percorso[inizio:], prossimo]
            if colore.get(prossimo) == BIANCO:
                trovato = scendi(prossimo)
                if trovato:
                    return trovato
        colore[nodo] = NERO
        percorso.pop()
        return []

    for nodo in grafo.mappa:
        if colore[nodo] == BIANCO:
            anello = scendi(nodo)
            if anello:
                return anello
    return []


# --------------------------------------------------------------------------
# Il percorso
# --------------------------------------------------------------------------


def valuta_condizione(
    dati: Mapping[str, Any],
    adesso: datetime,
    stati: Optional[Mapping[str, str]] = None,
    casa_abitata: Optional[bool] = None,
) -> tuple[str, str]:
    """Quale ramo prende questa condizione, e perche'.

    Il motivo torna anche quando il ramo e' «vero», vuoto: chi guarda la
    simulazione vuole leggere *perche'* si e' andati di la', e un ramo senza
    spiegazione e' indistinguibile da un ramo preso a caso.
    """
    condizione = dati.get("condizione") or dati
    motivo = regole.motivo_condizione(condizione, adesso, stati, casa_abitata)
    return (FALSO, motivo) if motivo else (VERO, "")


def percorso(
    grafo: Grafo,
    adesso: datetime,
    stati: Optional[Mapping[str, str]] = None,
    casa_abitata: Optional[bool] = None,
) -> tuple[list[Passo], list[tuple[str, str, str]]]:
    """I nodi da eseguire, in ordine, e le decisioni prese lungo la strada.

    Le decisioni tornano insieme al percorso perche' servono a due cose che
    non si possono ricavare dopo: illuminare il ramo giusto nel simulatore, e
    rispondere a «perche' la routine non ha acceso la luce» senza rieseguirla.

    I nodi trigger non finiscono nel percorso: dicono *quando* partire, non
    cosa fare. Eseguirli sarebbe eseguire il proprio innesco.

    **Un anello non fa girare a vuoto**, e non serve un tetto ai passi per
    ottenerlo: `visti` fa si' che ogni nodo si esegua una volta sola, quindi
    il percorso e' lungo al massimo quanto il grafo. Un tetto c'era, e non
    poteva scattare mai: l'ho scoperto perche' toglierlo non faceva fallire
    nessun test.
    """
    passi: list[Passo] = []
    decisioni: list[tuple[str, str, str]] = []
    visti: set[str] = set()
    coda = list(grafo.inizi())

    while coda:
        corrente = coda.pop(0)
        if corrente in visti:
            continue
        visti.add(corrente)

        tipo = grafo.tipo_di(corrente)

        if tipo == CONDIZIONE:
            ramo, motivo = valuta_condizione(grafo.dati_di(corrente), adesso, stati, casa_abitata)
            decisioni.append((corrente, ramo, motivo))
            coda.extend(grafo.successivi(corrente, ramo))
            continue

        if tipo != TRIGGER:
            passi.append(Passo(corrente, tipo, grafo.dati_di(corrente)))

        coda.extend(grafo.successivi(corrente))

    return passi, decisioni


def descrivi_problemi(problemi: Iterable[Problema]) -> str:
    """I problemi in una frase sola, per chi riceve un errore e basta."""
    elenco = list(problemi)
    if not elenco:
        return ""
    return " ".join(p.messaggio for p in elenco)
