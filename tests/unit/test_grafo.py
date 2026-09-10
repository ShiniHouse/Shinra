"""Il grafo di una routine: cosa viene dopo cosa, e cosa non torna.

Finora l'esecutore percorreva **tutti** gli archi, e con quattro tipi di nodo
bastava: il flusso era sempre lineare, non c'era niente da decidere. Il test
piu' importante di questo file e'
`test_una_condizione_percorre_un_ramo_solo`: una visita che li percorre
entrambi non e' una condizione, e' una decorazione — e passerebbe tutti gli
altri test.

Il secondo per importanza e' `test_i_problemi_dicono_quali_nodi`: «il grafo non
e' valido» manda a guardare trenta nodi, e chi ha disegnato trenta nodi non lo
fa — salva lo stesso, o rinuncia.

Riferimento: issue #28.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from shinra.domain import grafo as dominio

ADESSO = datetime(2026, 9, 10, 21, 0)  # un giovedi' sera


def _n(identificativo: str, tipo: str, **dati) -> dict:
    return {"id": identificativo, "type": tipo, "data": dati}


def _a(partenza: str, arrivo: str, ramo: str | None = None) -> dict:
    arco = {"from": partenza, "to": arrivo}
    if ramo:
        arco["ramo"] = ramo
    return arco


def _percorso(nodi, archi, **contesto) -> list[str]:
    passi, _ = dominio.percorso(dominio.Grafo(nodi, archi), contesto.pop("adesso", ADESSO), **contesto)
    return [p.id for p in passi]


# ======================================================= il percorso lineare


def test_una_routine_lineare_esegue_tutto_in_ordine():
    """Il comportamento che c'era prima, e che non deve cambiare: le routine
    gia' salvate sono lineari."""
    nodi = [
        _n("t", dominio.TRIGGER),
        _n("luce", dominio.DISPOSITIVO, entity_id="light.salotto"),
        _n("attesa", dominio.RITARDO, seconds=5),
        _n("voce", dominio.ANNUNCIO, message="fatto"),
    ]
    archi = [_a("t", "luce"), _a("luce", "attesa"), _a("attesa", "voce")]

    assert _percorso(nodi, archi) == ["luce", "attesa", "voce"]


def test_il_nodo_trigger_non_viene_eseguito():
    """Dice *quando* partire, non cosa fare: eseguirlo sarebbe eseguire il
    proprio innesco."""
    nodi = [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO)]

    assert _percorso(nodi, [_a("t", "luce")]) == ["luce"]


def test_senza_nodo_trigger_si_parte_da_chi_non_ha_ingressi():
    """Alcune routine salvate non hanno un nodo trigger e cominciano dal primo
    nodo disegnato: romperle sarebbe un prezzo che nessuno ha chiesto."""
    nodi = [_n("a", dominio.DISPOSITIVO), _n("b", dominio.ANNUNCIO)]

    assert _percorso(nodi, [_a("a", "b")]) == ["a", "b"]


def test_un_grafo_tutto_anello_non_manda_in_crisi_l_esecuzione():
    """Non e' salvabile — la validazione lo rifiuta — ma potrebbe essere gia'
    salvato da prima, e una casa che si pianta e' peggio di una routine che si
    ferma."""
    nodi = [_n("a", dominio.DISPOSITIVO), _n("b", dominio.DISPOSITIVO)]

    assert _percorso(nodi, [_a("a", "b"), _a("b", "a")]) == ["a", "b"]


# ========================================================== le condizioni


def test_una_condizione_percorre_un_ramo_solo():
    """Il cuore della issue. Una visita che percorre entrambi i rami passa
    tutti gli altri test di questo file e non e' una condizione."""
    nodi = [
        _n("t", dominio.TRIGGER),
        _n("se", dominio.CONDIZIONE, condizione={"tipo": "presenza", "abitata": True}),
        _n("si", dominio.ANNUNCIO, message="bentornato"),
        _n("no", dominio.DISPOSITIVO, entity_id="light.tutte", action="turn_off"),
    ]
    archi = [_a("t", "se"), _a("se", "si", dominio.VERO), _a("se", "no", dominio.FALSO)]

    assert _percorso(nodi, archi, casa_abitata=True) == ["si"]
    assert _percorso(nodi, archi, casa_abitata=False) == ["no"]


def test_il_ramo_preso_e_il_motivo_tornano_insieme_al_percorso():
    """Servono a due cose che non si ricavano dopo: illuminare il ramo giusto
    nel simulatore, e rispondere a «perche' non ha acceso la luce» senza
    rieseguire la routine."""
    nodi = [
        _n(
            "se",
            dominio.CONDIZIONE,
            condizione={"tipo": "stato_entita", "entity_id": "light.x", "stato": "on"},
        ),
        _n("si", dominio.ANNUNCIO),
        _n("no", dominio.ANNUNCIO),
    ]
    archi = [_a("se", "si", dominio.VERO), _a("se", "no", dominio.FALSO)]

    _, decisioni = dominio.percorso(dominio.Grafo(nodi, archi), ADESSO, {"light.x": "off"})

    assert len(decisioni) == 1
    nodo, ramo, motivo = decisioni[0]
    assert (nodo, ramo) == ("se", dominio.FALSO)
    assert "off" in motivo and "on" in motivo


def test_una_condizione_vera_non_porta_un_motivo():
    nodi = [_n("se", dominio.CONDIZIONE, condizione={"tipo": "presenza", "abitata": True})]

    _, decisioni = dominio.percorso(dominio.Grafo(nodi, []), ADESSO, casa_abitata=True)

    assert decisioni == [("se", dominio.VERO, "")]


def test_la_condizione_usa_il_vocabolario_della_issue_27():
    """Non un vocabolario nuovo: `regole.motivo_condizione` risponde alla
    stessa domanda per il motore di regole e per un nodo del grafo. Due
    implementazioni divergerebbero, e la divergenza si vedrebbe come «la
    stessa condizione si comporta diversamente a seconda di dove l'hai
    scritta»."""
    sera = {"tipo": "fra_le_ore", "dalle": "20:00", "alle": "23:00"}

    assert dominio.valuta_condizione({"condizione": sera}, ADESSO)[0] == dominio.VERO
    assert dominio.valuta_condizione({"condizione": sera}, ADESSO.replace(hour=9))[0] == dominio.FALSO


def test_la_condizione_si_puo_scrivere_anche_senza_involucro():
    """Alcuni editor scrivono i campi direttamente nel nodo invece che dentro
    `condizione`. Rifiutarli produrrebbe un ramo sempre vero, che e' il modo
    peggiore di sbagliare: sembra funzionare."""
    piatta = {"tipo": "presenza", "abitata": False}

    assert dominio.valuta_condizione(piatta, ADESSO, casa_abitata=False)[0] == dominio.VERO


def test_un_arco_senza_etichetta_da_una_condizione_viene_percorso_comunque():
    """E' un disegno vecchio o un errore, ma interromperlo in silenzio
    romperebbe routine che oggi funzionano."""
    nodi = [
        _n("se", dominio.CONDIZIONE, condizione={"tipo": "presenza", "abitata": True}),
        _n("sempre", dominio.ANNUNCIO),
    ]

    assert _percorso(nodi, [_a("se", "sempre")], casa_abitata=True) == ["sempre"]
    assert _percorso(nodi, [_a("se", "sempre")], casa_abitata=False) == ["sempre"]


def test_una_condizione_senza_niente_da_verificare_e_vera():
    """Un nodo appena trascinato e non ancora configurato non deve fermare
    l'intera routine mentre la si sta disegnando."""
    nodi = [_n("se", dominio.CONDIZIONE), _n("poi", dominio.ANNUNCIO)]

    assert _percorso(nodi, [_a("se", "poi", dominio.VERO)]) == ["poi"]


# ========================================================== la validazione


def _problemi(nodi, archi) -> set[str]:
    return {p.tipo for p in dominio.valida(nodi, archi)}


def test_un_grafo_lineare_non_ha_problemi():
    nodi = [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO)]

    assert dominio.valida(nodi, [_a("t", "luce")]) == []


def test_un_grafo_vuoto_non_e_un_errore():
    """E' una routine appena creata: rifiutarla vorrebbe dire non poterla
    cominciare."""
    assert dominio.valida([], []) == []


def test_un_nodo_scollegato_viene_segnalato():
    """Non e' un dettaglio estetico: e' lavoro disegnato che non verra' mai
    fatto, e guardando il grafo non si vede."""
    nodi = [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO), _n("orfano", dominio.ANNUNCIO)]

    assert dominio.NODO_SCOLLEGATO in _problemi(nodi, [_a("t", "luce")])


def test_un_ciclo_viene_segnalato_con_i_nodi_dell_anello():
    nodi = [_n("t", dominio.TRIGGER), _n("a", dominio.DISPOSITIVO), _n("b", dominio.DISPOSITIVO)]
    archi = [_a("t", "a"), _a("a", "b"), _a("b", "a")]

    problemi = [p for p in dominio.valida(nodi, archi) if p.tipo == dominio.CICLO]

    assert problemi, "un ciclo non segnalato diventa una routine che non finisce"
    assert set(problemi[0].nodi) == {"a", "b"}


def test_una_condizione_con_un_ramo_solo_viene_segnalata():
    """Non e' una condizione: e' un filtro che a volte ferma tutto, e chi l'ha
    disegnata si aspetta due strade."""
    nodi = [_n("se", dominio.CONDIZIONE), _n("si", dominio.ANNUNCIO)]

    assert dominio.RAMO_SENZA_USCITA in _problemi(nodi, [_a("se", "si", dominio.VERO)])


def test_una_condizione_con_due_rami_va_bene():
    nodi = [_n("se", dominio.CONDIZIONE), _n("si", dominio.ANNUNCIO), _n("no", dominio.ANNUNCIO)]
    archi = [_a("se", "si", dominio.VERO), _a("se", "no", dominio.FALSO)]

    assert dominio.RAMO_SENZA_USCITA not in _problemi(nodi, archi)


def test_un_arco_verso_il_vuoto_viene_segnalato():
    nodi = [_n("a", dominio.DISPOSITIVO)]

    assert dominio.ARCO_ROTTO in _problemi(nodi, [_a("a", "sparito")])


def test_un_tipo_di_nodo_sconosciuto_viene_segnalato():
    """Un nodo cosi' non da' errore: viene saltato in silenzio, e chi l'ha
    disegnato crede che funzioni."""
    nodi = [_n("t", dominio.TRIGGER), _n("boh", "qualcosa_di_nuovo")]

    assert dominio.TIPO_SCONOSCIUTO in _problemi(nodi, [_a("t", "boh")])


def test_i_problemi_dicono_quali_nodi():
    """«Il grafo non e' valido» manda a guardarli tutti. Chi ha disegnato
    trenta nodi non lo fa: salva lo stesso, o rinuncia."""
    nodi = [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO), _n("orfano", dominio.ANNUNCIO)]

    problemi = dominio.valida(nodi, [_a("t", "luce")])

    scollegati = [p for p in problemi if p.tipo == dominio.NODO_SCOLLEGATO]
    assert scollegati[0].nodi == ("orfano",)


def test_i_problemi_si_riportano_tutti_non_solo_il_primo():
    """Chi ha disegnato un grafo sbagliato in tre punti vuole saperlo una
    volta sola, non tre salvataggi di fila."""
    nodi = [
        _n("t", dominio.TRIGGER),
        _n("se", dominio.CONDIZIONE),
        _n("si", dominio.ANNUNCIO),
        _n("orfano", dominio.ANNUNCIO),
        _n("boh", "tipo_inventato"),
    ]

    tipi = _problemi(nodi, [_a("t", "se"), _a("se", "si", dominio.VERO)])

    assert {dominio.RAMO_SENZA_USCITA, dominio.NODO_SCOLLEGATO, dominio.TIPO_SCONOSCIUTO} <= tipi


def test_senza_trigger_ogni_catena_e_un_inizio_e_nessuna_e_orfana():
    """Il comportamento che c'era prima: piu' radici vogliono dire piu'
    catene, e si eseguono tutte. Segnalarle come scollegate direbbe che sono
    rotte routine che funzionano da sempre."""
    nodi = [_n("a", dominio.DISPOSITIVO), _n("b", dominio.ANNUNCIO), _n("c", dominio.ANNUNCIO)]

    assert dominio.NODO_SCOLLEGATO not in _problemi(nodi, [_a("a", "b")])
    assert set(_percorso(nodi, [_a("a", "b")])) == {"a", "b", "c"}


def test_con_un_trigger_le_altre_catene_diventano_orfane():
    """L'altra meta': appena c'e' un innesco, e' quello a decidere da dove si
    parte, e una catena che non ne discende non verra' mai eseguita."""
    nodi = [_n("t", dominio.TRIGGER), _n("a", dominio.DISPOSITIVO), _n("b", dominio.ANNUNCIO)]

    assert dominio.NODO_SCOLLEGATO in _problemi(nodi, [_a("t", "a")])
    assert _percorso(nodi, [_a("t", "a")]) == ["a"]


def test_un_nodo_raggiungibile_solo_dal_ramo_falso_e_collegato():
    """La domanda della validazione non e' «cosa verra' eseguito stasera» ma
    «cosa potrebbe esserlo»: un nodo sul ramo falso e' collegato anche se
    stasera non ci si passa."""
    nodi = [_n("se", dominio.CONDIZIONE), _n("si", dominio.ANNUNCIO), _n("no", dominio.ANNUNCIO)]
    archi = [_a("se", "si", dominio.VERO), _a("se", "no", dominio.FALSO)]

    assert dominio.NODO_SCOLLEGATO not in _problemi(nodi, archi)


def test_un_grafo_senza_inizio_viene_segnalato():
    nodi = [_n("a", dominio.DISPOSITIVO), _n("b", dominio.DISPOSITIVO)]

    assert dominio.SENZA_INIZIO in _problemi(nodi, [_a("a", "b"), _a("b", "a")])


@pytest.mark.parametrize(
    "tipo", [dominio.NODO_SCOLLEGATO, dominio.CICLO, dominio.RAMO_SENZA_USCITA, dominio.SENZA_INIZIO]
)
def test_ogni_problema_ha_un_messaggio_leggibile(tipo):
    """Un codice di errore da solo non ripara niente."""
    problema = dominio.Problema(tipo, "x")

    assert problema.tipo == tipo
    assert dominio.descrivi_problemi([problema]) == "x"
