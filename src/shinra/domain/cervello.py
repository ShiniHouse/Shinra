"""Tutto quello che Shinra sa e fa, come grafo (issue #185).

La scheda «Il Cervello» mostra nodi e collegamenti. Il materiale esiste gia' nel
database e nel codice — stanze, dispositivi, alias, routine, regole, conoscenza,
strumenti — ma nessuno lo aveva mai messo insieme. Questo modulo lo fa senza
toccare niente: entrano elenchi di dizionari, esce il grafo. Niente rete, niente
database, niente FastAPI: e' il dominio, e si prova con quattro righe.

**I collegamenti sono veri.** Un cavo dice una cosa che il sistema sa: un alias
che nomina quel dispositivo, una regola che lo comanda, una routine che lo
tocca. Un collegamento decorativo — tirato fra due nodi perche' il disegno
viene meglio — trasformerebbe la scheda in un'illustrazione, e chi la guarda
crederebbe di capire la casa senza capirla.

**Nessun collegamento punta nel vuoto.** Un cavo verso un dispositivo che la casa
non conosce piu' (l'alias di una lampadina sostituita) non diventa un nodo
fantasma: si scarta, e il contatore non lo conta.

**Il contenuto della conoscenza non esce.** Un fatto e' una frase scritta da chi
abita qui — «il codice del cancello e...» — e questo grafo arriva nel browser e
nella pagina di chiunque abbia una sessione. Esce che il fatto esiste e di che
argomento e', mai cosa dice.

**Un tetto ai nodi.** Con centinaia di dispositivi il grafo diventa una nebbia, e
un browser su un tablet a muro non la regge. Oltre il tetto si tengono i nodi
piu' importanti e gli altri si contano per cluster (`nascosti`): si vede che
esistono senza doverli disegnare.

Riferimento: issue #185.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

# Stati di un sistema. Sono tre e non due perche' «fermo» e «non raggiungibile»
# si correggono in modi diversi: il primo e' una scelta (una regola spenta), il
# secondo un guasto (Home Assistant non risponde).
ATTIVO = "attivo"
FERMO = "fermo"
NON_RAGGIUNGIBILE = "non_raggiungibile"
STATI = (ATTIVO, FERMO, NON_RAGGIUNGIBILE)

# I cluster, nell'ordine in cui si tengono i nodi quando ce ne sono troppi:
# prima cio' che da' forma alla casa, per ultimo cio' che la riempie.
CLUSTER: Dict[str, str] = {
    "stanze": "Stanze",
    "routine": "Routine",
    "regole": "Regole",
    "dispositivi": "Dispositivi",
    "alias": "Alias",
    "strumenti": "Strumenti",
    "agenti": "Agenti",
    "conoscenza": "Conoscenza",
}

MASSIMO_NODI = 400


def _entita_in(oggetto: Any) -> Iterator[str]:
    """Ogni `entity_id` scritto dentro una struttura qualunque.

    Le azioni, le condizioni e i nodi di una routine hanno forme diverse, e
    cambiano a ogni tipo nuovo. Invece di conoscerle una per una si cerca la
    chiave, dappertutto: e' l'unica cosa che hanno in comune, ed e' quella che
    serve a disegnare il cavo.
    """
    if isinstance(oggetto, dict):
        for chiave, valore in oggetto.items():
            if chiave == "entity_id" and isinstance(valore, str) and valore.strip():
                yield valore.strip()
            else:
                yield from _entita_in(valore)
    elif isinstance(oggetto, (list, tuple)):
        for elemento in oggetto:
            yield from _entita_in(elemento)


def _chiave_stanza(nome: str) -> str:
    return " ".join(nome.split()).casefold()


def costruisci(
    *,
    alias: Iterable[Dict[str, Any]] = (),
    routine: Iterable[Dict[str, Any]] = (),
    regole: Iterable[Dict[str, Any]] = (),
    fatti: Iterable[Dict[str, Any]] = (),
    strumenti: Iterable[Dict[str, Any]] = (),
    agenti: Iterable[Dict[str, Any]] = (),
    sistemi: Iterable[Dict[str, Any]] = (),
    vede_conoscenza: bool = True,
    massimo_nodi: int = MASSIMO_NODI,
) -> Dict[str, Any]:
    """Il grafo: `{nodi, collegamenti, clusters, sistemi, contatori, troncato}`."""
    nodi: Dict[str, Dict[str, Any]] = {}
    collegamenti: List[Dict[str, str]] = []

    def nodo(id_: str, tipo: str, nome: str, cluster: str, **extra: Any) -> None:
        if id_ not in nodi:
            nodi[id_] = {"id": id_, "tipo": tipo, "nome": nome, "cluster": cluster, **extra}

    def cavo(da: str, a: str, tipo: str) -> None:
        collegamenti.append({"da": da, "a": a, "tipo": tipo})

    # --- stanze, alias e dispositivi ---------------------------------------
    nomi_dispositivo: Dict[str, str] = {}
    for voce in alias:
        entita = str(voce.get("entity_id") or "").strip()
        nome_alias = str(voce.get("alias") or "").strip()
        if not entita or not nome_alias:
            continue
        id_alias = f"alias:{voce.get('id') or nome_alias.casefold()}"
        nodo(id_alias, "alias", nome_alias, "alias")
        nomi_dispositivo.setdefault(entita, nome_alias)
        nodo(f"dispositivo:{entita}", "dispositivo", nome_alias, "dispositivi", entita=entita)
        cavo(id_alias, f"dispositivo:{entita}", "chiama")
        stanza = str(voce.get("room") or "").strip()
        if stanza:
            id_stanza = f"stanza:{_chiave_stanza(stanza)}"
            nodo(id_stanza, "stanza", stanza, "stanze")
            cavo(f"dispositivo:{entita}", id_stanza, "sta_in")

    def dispositivo_noto(entita: str) -> Optional[str]:
        """Il nodo di un'entita', se la casa la conosce; se no niente.

        Una regola puo' comandare un'entita' che non ha nessun alias: e'
        legittimo, ma non avendo un nome da mostrare diventerebbe un nodo con
        il codice al posto del nome. Si crea lo stesso — e' una cosa che la
        casa comanda davvero — con `entity_id` come nome.
        """
        id_ = f"dispositivo:{entita}"
        if id_ not in nodi:
            nodo(id_, "dispositivo", nomi_dispositivo.get(entita, entita), "dispositivi", entita=entita)
        return id_

    # --- routine -----------------------------------------------------------
    for voce in routine:
        id_routine = f"routine:{voce.get('id')}"
        nome_routine = str(voce.get("name") or voce.get("id") or "").strip()
        if not voce.get("id") or not nome_routine:
            continue
        nodo(
            id_routine,
            "routine",
            nome_routine,
            "routine",
            stato=ATTIVO if voce.get("enabled", True) else FERMO,
        )
        visti: Set[str] = set()
        for entita in _entita_in([voce.get("nodes"), voce.get("actions")]):
            if entita in visti:
                continue
            visti.add(entita)
            cavo(id_routine, dispositivo_noto(entita) or "", "comanda")

    # --- regole ------------------------------------------------------------
    for voce in regole:
        if not voce.get("id"):
            continue
        id_regola = f"regola:{voce['id']}"
        nodo(
            id_regola,
            "regola",
            str(voce.get("nome") or voce["id"]),
            "regole",
            stato=ATTIVO if voce.get("attiva", True) else FERMO,
        )
        origine = str(voce.get("origine") or "")
        if origine.startswith("grafo:"):
            cavo(id_regola, f"routine:{origine[len('grafo:'):]}", "nasce_da")
        visti = set()
        for entita in _entita_in([voce.get("azioni"), voce.get("condizioni"), voce.get("trigger")]):
            if entita in visti:
                continue
            visti.add(entita)
            cavo(id_regola, dispositivo_noto(entita) or "", "comanda")

    # --- strumenti e agenti -------------------------------------------------
    for voce in strumenti:
        nome_strumento = str(voce.get("nome") or "").strip()
        if not nome_strumento:
            continue
        dominio = str(voce.get("dominio") or "").strip()
        nodo(f"strumento:{nome_strumento}", "strumento", nome_strumento, "strumenti", dominio=dominio)
        if dominio:
            nodo(f"dominio:{dominio}", "dominio", dominio, "strumenti")
            cavo(f"strumento:{nome_strumento}", f"dominio:{dominio}", "appartiene")

    agenti_pronti = 0
    for voce in agenti:
        nome_agente = str(voce.get("nome") or "").strip()
        if not nome_agente:
            continue
        pronto = bool(voce.get("pronto", True))
        agenti_pronti += 1 if pronto else 0
        nodo(f"agente:{nome_agente}", "agente", nome_agente, "agenti", stato=ATTIVO if pronto else FERMO)
        for nome_strumento in voce.get("strumenti") or ():
            cavo(f"agente:{nome_agente}", f"strumento:{nome_strumento}", "usa")

    # --- conoscenza: il contenuto non esce ----------------------------------
    if vede_conoscenza:
        for voce in fatti:
            if not voce.get("id"):
                continue
            argomento = str(voce.get("category") or "generale").strip() or "generale"
            nodo(f"argomento:{argomento.casefold()}", "argomento", argomento, "conoscenza")
            nodo(
                f"fatto:{voce['id']}",
                "fatto",
                argomento,  # l'argomento, non il testo: il testo non esce mai
                "conoscenza",
                stato=ATTIVO if voce.get("enabled", True) else FERMO,
            )
            cavo(f"fatto:{voce['id']}", f"argomento:{argomento.casefold()}", "riguarda")

    # --- niente cavi nel vuoto, niente doppioni ------------------------------
    visti_cavi: Set[tuple] = set()
    validi: List[Dict[str, str]] = []
    for c in collegamenti:
        chiave = (c["da"], c["a"], c["tipo"])
        if c["da"] in nodi and c["a"] in nodi and chiave not in visti_cavi:
            visti_cavi.add(chiave)
            validi.append(c)

    # --- il tetto ---------------------------------------------------------
    ordine = list(CLUSTER)
    per_cluster: Dict[str, List[str]] = {nome: [] for nome in ordine}
    for id_, n in nodi.items():
        per_cluster.setdefault(n["cluster"], []).append(id_)

    tenuti: Set[str] = set()
    for nome_cluster in ordine:
        for id_ in per_cluster.get(nome_cluster, []):
            if len(tenuti) < massimo_nodi:
                tenuti.add(id_)
    troncato = len(tenuti) < len(nodi)

    clusters = []
    for nome_cluster in ordine:
        ids = per_cluster.get(nome_cluster, [])
        if not ids:
            continue
        nascosti = sum(1 for i in ids if i not in tenuti)
        clusters.append(
            {
                "id": nome_cluster,
                "nome": CLUSTER[nome_cluster],
                "nodi": len(ids) - nascosti,
                "nascosti": nascosti,
            }
        )

    nodi_finali = [nodi[i] for nome in ordine for i in per_cluster.get(nome, []) if i in tenuti]
    cavi_finali = [cavo_ for cavo_ in validi if cavo_["da"] in tenuti and cavo_["a"] in tenuti]

    sistemi_lista = [_sistema(s) for s in sistemi]
    attivi = sum(1 for s in sistemi_lista if s["stato"] == ATTIVO)

    return {
        "nodi": nodi_finali,
        "collegamenti": cavi_finali,
        "clusters": clusters,
        "sistemi": sistemi_lista,
        "contatori": {
            "nodi": len(nodi_finali),
            "collegamenti": len(cavi_finali),
            "sistemi": len(sistemi_lista),
            "sistemi_attivi": attivi,
            "agenti_pronti": agenti_pronti,
        },
        "troncato": troncato,
    }


def _sistema(voce: Dict[str, Any]) -> Dict[str, Any]:
    """Un sistema con uno stato che esiste: uno sconosciuto conta come guasto.

    Un sistema che dichiara uno stato inventato non deve passare per «attivo»
    per distrazione: e' il modo in cui il contatore mentirebbe verso l'alto.
    """
    stato = voce.get("stato")
    if stato not in STATI:
        stato = NON_RAGGIUNGIBILE
    return {
        "id": str(voce.get("id") or ""),
        "nome": str(voce.get("nome") or voce.get("id") or ""),
        "cluster": voce.get("cluster") or "",
        "stato": stato,
        "motivo": "" if stato == ATTIVO else str(voce.get("motivo") or ""),
    }
