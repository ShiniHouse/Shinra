"""I nodi trigger: cosa fa partire una routine, e cosa non la fara' partire.

Il test piu' importante di questo file e'
`test_un_innesco_incompleto_non_diventa_una_regola`. La ragione e' che un
trigger incompleto **non da' nessun errore**: `domain/regole` ha un ripiego per
ogni campo — le sette del mattino se l'ora manca — e i ripieghi sono giusti per
chi scrive una regola a mano e sbagliati per chi ha disegnato un nodo e non
l'ha compilato. Una routine che scatta alle sette invece che alle ventitre' non
sembra rotta: sembra sbagliata, ed e' molto piu' difficile da capire.

Il secondo e' `test_una_routine_gia_salvata_resta_vocale`: ogni routine
esistente ha un nodo trigger senza niente dentro, e se questo modulo le
leggesse come inneschi automatici la casa comincerebbe a fare da sola cose che
nessuno le ha chiesto.

Riferimento: issue #28.
"""

from __future__ import annotations

import pytest

from shinra.domain import grafo as dominio
from shinra.domain import regole


def _n(identificativo: str, tipo: str, **dati) -> dict:
    return {"id": identificativo, "type": tipo, "data": dati}


def _tipi_di_problema(nodi, archi) -> list[str]:
    return [p.tipo for p in dominio.valida(nodi, archi)]


# ============================================== il ripiego delle routine vecchie


def test_una_routine_gia_salvata_resta_vocale():
    """Nessun `trigger` nei dati vuol dire innesco vocale.

    E' il caso di **ogni** routine salvata finora. Leggerlo come qualcos'altro
    vorrebbe dire che aggiornando Shinra la casa comincia a fare da sola cose
    che nessuno le ha chiesto.
    """
    assert dominio.trigger_del_nodo({})["tipo"] == dominio.VOCE
    assert dominio.trigger_del_nodo({"phrases": ["cinema"]})["tipo"] == dominio.VOCE


def test_un_trigger_che_non_e_un_dizionario_non_fa_esplodere_niente():
    """Un `trigger` che e' una stringa e' un disegno corrotto, non un motivo
    per non aprire piu' la routine."""
    assert dominio.trigger_del_nodo({"trigger": "orario"})["tipo"] == dominio.VOCE


def test_il_tipo_si_legge_senza_badare_a_spazi_e_maiuscole():
    letto = dominio.trigger_del_nodo({"trigger": {"tipo": "  Orario "}})

    assert letto["tipo"] == regole.ORARIO


def test_gli_altri_campi_del_trigger_arrivano_interi():
    letto = dominio.trigger_del_nodo({"trigger": {"tipo": "orario", "ora": "23:30", "giorni": [0, 1]}})

    assert letto["ora"] == "23:30"
    assert letto["giorni"] == [0, 1]


# ========================================================= cosa manca a un innesco


def test_un_innesco_vocale_non_manca_di_niente():
    assert dominio.perche_non_scattera({"tipo": dominio.VOCE}) is None


@pytest.mark.parametrize(
    "trigger",
    [
        {"tipo": regole.ORARIO, "ora": "07:00"},
        {"tipo": regole.ALBA},
        {"tipo": regole.TRAMONTO, "scarto_minuti": -20},
        {"tipo": regole.EVENTO, "evento": "casa.vuota"},
        {"tipo": regole.STATO, "entity_id": "sensor.t", "valore": 15},
    ],
)
def test_un_innesco_completo_va_bene(trigger):
    assert dominio.perche_non_scattera(trigger) is None


def test_un_orario_senza_ora_lo_dice():
    """Senza questo controllo la routine scatterebbe alle sette del mattino,
    che e' il ripiego di `domain/regole`, e nessuno saprebbe perche'."""
    assert dominio.perche_non_scattera({"tipo": regole.ORARIO}) == "manca l'ora"
    assert dominio.perche_non_scattera({"tipo": regole.ORARIO, "ora": "  "}) == "manca l'ora"


def test_un_evento_senza_nome_lo_dice():
    assert dominio.perche_non_scattera({"tipo": regole.EVENTO}) == "manca il nome dell'evento"


def test_uno_stato_senza_entita_lo_dice():
    assert dominio.perche_non_scattera({"tipo": regole.STATO, "valore": 15}) == (
        "manca l'entita' da sorvegliare"
    )


def test_uno_stato_senza_valore_lo_dice():
    """Uno zero e' un valore, una stringa vuota no: sorvegliare «scende sotto
    zero» e' una richiesta legittima, e rifiutarla sarebbe un difetto."""
    assert dominio.perche_non_scattera({"tipo": regole.STATO, "entity_id": "sensor.t"}) == (
        "manca il valore da confrontare"
    )
    assert dominio.perche_non_scattera({"tipo": regole.STATO, "entity_id": "sensor.t", "valore": 0}) is None


def test_un_tipo_inventato_lo_dice_e_lo_ripete():
    """Il messaggio porta con se' il tipo scritto: «non conosco questo
    innesco» non dice quale, e in un grafo con tre inneschi non basta."""
    motivo = dominio.perche_non_scattera({"tipo": "quando_mi_va"})

    assert motivo is not None
    assert "quando_mi_va" in motivo


# ================================================== quali inneschi sono automatici


def test_l_innesco_vocale_non_e_automatico():
    """Non ha bisogno di nessuno che lo aspetti: programmare qualcosa per una
    frase che potrebbe non essere mai detta non ha senso."""
    nodi = [_n("t", dominio.TRIGGER)]

    assert dominio.triggers_automatici(nodi) == []


def test_un_innesco_a_orario_e_automatico():
    nodi = [_n("t", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "23:30"})]

    trovati = dominio.triggers_automatici(nodi)

    assert [i for i, _ in trovati] == ["t"]
    assert trovati[0][1]["ora"] == "23:30"


def test_un_innesco_incompleto_non_diventa_una_regola():
    """Il test piu' importante di questo file.

    Programmare un trigger senza ora vorrebbe dire mettere nello scheduler la
    sua ora di ripiego — le sette del mattino — e una routine che scatta alle
    sette invece che alle ventitre' non sembra rotta: sembra sbagliata.
    """
    nodi = [_n("t", dominio.TRIGGER, trigger={"tipo": "orario"})]

    assert dominio.triggers_automatici(nodi) == []


def test_solo_i_nodi_trigger_contano():
    """Una condizione con dentro un `trigger` e' un disegno strano, non un
    innesco: se lo fosse, la routine partirebbe da meta' di se stessa."""
    nodi = [
        _n("c", dominio.CONDIZIONE, trigger={"tipo": "orario", "ora": "07:00"}),
        _n("luce", dominio.DISPOSITIVO, trigger={"tipo": "alba"}),
    ]

    assert dominio.triggers_automatici(nodi) == []


def test_due_inneschi_automatici_sono_due():
    """Una routine puo' partire all'alba **e** alle ventitre': sono due
    programmazioni, e collassarle in una perderebbe una delle due."""
    nodi = [
        _n("a", dominio.TRIGGER, trigger={"tipo": "alba"}),
        _n("b", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "23:00"}),
    ]

    assert sorted(i for i, _ in dominio.triggers_automatici(nodi)) == ["a", "b"]


def test_un_nodo_senza_identificativo_viene_ignorato():
    assert (
        dominio.triggers_automatici([{"type": dominio.TRIGGER, "data": {"trigger": {"tipo": "alba"}}}]) == []
    )


# ============================================== la validazione degli inneschi


def test_un_innesco_incompleto_e_un_problema_del_grafo():
    nodi = [_n("t", dominio.TRIGGER, trigger={"tipo": "orario"}), _n("luce", dominio.DISPOSITIVO)]

    assert dominio.TRIGGER_MUTO in _tipi_di_problema(nodi, [{"from": "t", "to": "luce"}])


def test_il_problema_indica_il_nodo_e_dice_cosa_manca():
    """Un problema senza il nodo manda a guardarli tutti, e un problema senza
    il motivo non dice cosa compilare."""
    nodi = [_n("t", dominio.TRIGGER, trigger={"tipo": "stato", "valore": 15}), _n("l", dominio.DISPOSITIVO)]

    problema = next(
        p for p in dominio.valida(nodi, [{"from": "t", "to": "l"}]) if p.tipo == dominio.TRIGGER_MUTO
    )

    assert problema.nodi == ("t",)
    assert "entita'" in problema.messaggio


def test_due_inneschi_rotti_danno_due_problemi():
    """Il motivo cambia da nodo a nodo: «due inneschi sono incompleti» non
    dice a nessuno cosa compilare."""
    nodi = [
        _n("a", dominio.TRIGGER, trigger={"tipo": "orario"}),
        _n("b", dominio.TRIGGER, trigger={"tipo": "evento"}),
        _n("luce", dominio.DISPOSITIVO),
    ]
    archi = [{"from": "a", "to": "luce"}, {"from": "b", "to": "luce"}]

    muti = [p for p in dominio.valida(nodi, archi) if p.tipo == dominio.TRIGGER_MUTO]

    assert sorted(p.nodi[0] for p in muti) == ["a", "b"]


def test_un_innesco_vocale_non_e_mai_un_problema():
    nodi = [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO)]

    assert dominio.TRIGGER_MUTO not in _tipi_di_problema(nodi, [{"from": "t", "to": "luce"}])


def test_un_innesco_con_un_cavo_in_ingresso_e_un_problema():
    """L'esecutore non lo esegue: passa oltre e prosegue. Il disegno mostra
    un innesco che non innesca, e senza questo controllo niente lo dice."""
    nodi = [
        _n("t", dominio.TRIGGER),
        _n("luce", dominio.DISPOSITIVO),
        _n("t2", dominio.TRIGGER, trigger={"tipo": "alba"}),
    ]
    archi = [{"from": "t", "to": "luce"}, {"from": "luce", "to": "t2"}]

    problema = next(p for p in dominio.valida(nodi, archi) if p.tipo == dominio.TRIGGER_INCATENATO)

    assert problema.nodi == ("t2",)
