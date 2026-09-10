"""Un innesco disegnato diventa una regola del motore, non un secondo motore.

La scelta e' scritta nella scheda #28 e questi test la tengono ferma: un grafo
con un innesco all'alba **non** si porta dietro un suo scheduler. Due motori
che programmano la stessa casa si contendono lo stesso lavoro, e il secondo si
scopre solo quando la luce si accende due volte.

I due test che contano di piu':

`test_togliere_l_innesco_toglie_la_regola` — perche' il difetto opposto,
lasciare dietro la regola di un nodo cancellato, e' il piu' difficile da
diagnosticare che esista in una casa che agisce da sola: qualcosa si accende e
non c'e' niente che lo spieghi.

`test_una_regola_messa_a_tacere_resta_tale` — risalvare il disegno per
correggere un orario non deve riaccendere un'automazione che qualcuno aveva
zittito apposta.

Riferimento: issue #28, issue #27.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from shinra.domain import grafo as dominio
from shinra.domain import regole as regole_dominio
from shinra.infra.db import depositi
from shinra.services.regole import ORIGINE_GRAFO, motore_regole


def _n(identificativo: str, tipo: str, **dati) -> dict:
    return {"id": identificativo, "type": tipo, "data": dati}


def _a(partenza: str, arrivo: str) -> dict:
    return {"from": partenza, "to": arrivo}


def _routine(nodi, archi, identificativo="m1", nome="Buonanotte") -> dict:
    return {"id": identificativo, "name": nome, "enabled": True, "nodes": nodi, "edges": archi}


ALL_ALBA = [_n("t", dominio.TRIGGER, trigger={"tipo": "alba"}), _n("luce", dominio.DISPOSITIVO)]
ARCHI = [_a("t", "luce")]


@pytest.fixture(autouse=True)
def archivio_pulito():
    depositi.regole.sostituisci_tutto([])
    depositi.modalita.sostituisci_tutto([])
    yield
    depositi.regole.sostituisci_tutto([])


def _generate() -> list[dict]:
    return depositi.regole.per_origine(f"{ORIGINE_GRAFO}m1")


# ================================================== dal disegno alla regola


def test_un_innesco_automatico_diventa_una_regola():
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI))

    regole = _generate()

    assert len(regole) == 1
    assert regole[0]["trigger"]["tipo"] == regole_dominio.ALBA


def test_la_regola_generata_attiva_quella_routine():
    """Una regola che scatta e non fa partire la routine giusta e' peggio di
    una regola che non scatta: sembra funzionare."""
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI, nome="Buonanotte"))

    azioni = _generate()[0]["azioni"]

    assert azioni == [{"tipo": regole_dominio.AZIONE_MODALITA, "modalita": "Buonanotte"}]


def test_un_innesco_vocale_non_genera_niente():
    """E' il caso di ogni routine salvata finora: se ne generasse una, la casa
    comincerebbe a fare da sola cose che nessuno le ha chiesto."""
    motore_regole.sincronizza_dal_grafo(_routine([_n("t", dominio.TRIGGER)], []))

    assert _generate() == []


def test_il_nome_della_regola_dice_quando_scatta():
    """Nell'elenco delle regole ce ne saranno diverse generate: senza il
    quando, si distinguono solo aprendole una per una."""
    motore_regole.sincronizza_dal_grafo(
        _routine([_n("t", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "23:30"})], [])
    )

    assert _generate()[0]["nome"] == "Buonanotte, ogni giorno alle 23:30"


def test_due_inneschi_fanno_due_regole_distinte():
    """Una routine puo' partire all'alba **e** alle ventitre'. Se i due nodi
    generassero lo stesso identificativo, uno dei due sparirebbe in silenzio."""
    nodi = [
        _n("a", dominio.TRIGGER, trigger={"tipo": "alba"}),
        _n("b", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "23:00"}),
    ]

    motore_regole.sincronizza_dal_grafo(_routine(nodi, []))

    generate = _generate()
    assert len({r["id"] for r in generate}) == 2


def test_due_routine_diverse_non_si_calpestano():
    """Lo stesso identificativo di nodo in due routine diverse: se l'impronta
    guardasse solo il nodo, salvarne una cancellerebbe la regola dell'altra."""
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI, identificativo="m1"))
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI, identificativo="m2"))

    assert len(depositi.regole.per_origine(f"{ORIGINE_GRAFO}m1")) == 1
    assert len(depositi.regole.per_origine(f"{ORIGINE_GRAFO}m2")) == 1


# ================================================= risalvare, togliere, cancellare


def test_risalvare_non_duplica():
    """Con un identificativo casuale, in una settimana la stessa routine
    avrebbe dieci regole che fanno tutte la stessa cosa."""
    for _ in range(3):
        motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI))

    assert len(_generate()) == 1


def test_risalvare_aggiorna_l_orario():
    motore_regole.sincronizza_dal_grafo(
        _routine([_n("t", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "07:00"})], [])
    )
    motore_regole.sincronizza_dal_grafo(
        _routine([_n("t", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "23:30"})], [])
    )

    generate = _generate()
    assert len(generate) == 1
    assert generate[0]["trigger"]["ora"] == "23:30"


def test_rinominare_la_routine_aggiorna_l_azione():
    """L'azione porta il nome della routine: se non seguisse la rinomina, la
    regola scatterebbe e cercherebbe una modalita' che non esiste piu'."""
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI, nome="Vecchio"))
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI, nome="Nuovo"))

    assert _generate()[0]["azioni"][0]["modalita"] == "Nuovo"


def test_togliere_l_innesco_toglie_la_regola():
    """Il difetto opposto — lasciarla dietro — e' il piu' difficile da
    diagnosticare: qualcosa si accende e non c'e' niente che lo spieghi."""
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI))
    assert len(_generate()) == 1

    motore_regole.sincronizza_dal_grafo(_routine([_n("t", dominio.TRIGGER)], []))

    assert _generate() == []


def test_cancellare_la_routine_cancella_le_regole():
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI))

    rimosse = motore_regole.dimentica_il_grafo("m1")

    assert len(rimosse) == 1
    assert _generate() == []


def test_una_routine_senza_identificativo_non_genera_niente():
    """Succede solo per un errore di chiamata, e generare una regola con
    origine `grafo:` vorrebbe dire non poterla piu' ritrovare."""
    esito = motore_regole.sincronizza_dal_grafo({"name": "senza id", "nodes": ALL_ALBA})

    assert esito == {"scritte": [], "rimosse": []}
    assert depositi.regole.elenco() == []


# ============================================== cosa la sincronizzazione non tocca


def test_una_regola_messa_a_tacere_resta_tale():
    """Risalvare il disegno per correggere un orario non deve riaccendere
    un'automazione che qualcuno aveva zittito apposta."""
    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI))
    generata = _generate()[0]["id"]
    depositi.regole.aggiorna(generata, {"attiva": False})

    motore_regole.sincronizza_dal_grafo(_routine(ALL_ALBA, ARCHI))

    assert _generate()[0]["attiva"] is False


def test_le_regole_scritte_a_mano_non_si_toccano():
    """Sincronizzare guarda solo cio' che porta l'origine di questa routine:
    una sincronizzazione che cancellasse anche il resto sarebbe un modo molto
    efficiente di perdere le automazioni di casa."""
    a_mano = motore_regole.crea({"nome": "Scritta a mano", "trigger": {"tipo": "alba"}})

    motore_regole.sincronizza_dal_grafo(_routine([_n("t", dominio.TRIGGER)], []))

    assert depositi.regole.per_id(a_mano["id"]) is not None


def test_una_regola_a_mano_non_ha_origine():
    a_mano = motore_regole.crea({"nome": "Scritta a mano", "trigger": {"tipo": "alba"}})

    assert depositi.regole.per_id(a_mano["id"])["origine"] == ""


# ====================================== la prova che il vocabolario e' lo stesso


def test_la_regola_generata_sa_dire_quando_scattera():
    """La prova che il grafo e il motore parlano la stessa lingua.

    Se `domain/grafo` scrivesse un trigger che `domain/regole` non riconosce,
    tutto il resto passerebbe lo stesso: la regola verrebbe salvata, sarebbe
    attiva, e non scatterebbe mai. `prossimo_scatto` e' il posto dove la
    divergenza si vede.
    """
    motore_regole.sincronizza_dal_grafo(
        _routine([_n("t", dominio.TRIGGER, trigger={"tipo": "orario", "ora": "23:30"})], [])
    )
    riga = _generate()[0]
    regola = regole_dominio.Regola(identificativo=riga["id"], nome=riga["nome"], trigger=riga["trigger"])

    quando = regole_dominio.prossimo_scatto(regola, datetime(2026, 9, 10, 8, 0))

    assert quando == datetime(2026, 9, 10, 23, 30)


def test_la_regola_generata_scatta_sull_evento_giusto():
    """L'altra meta': un innesco su evento deve essere riconosciuto dal
    motore quando l'evento passa sul bus."""
    motore_regole.sincronizza_dal_grafo(
        _routine([_n("t", dominio.TRIGGER, trigger={"tipo": "evento", "evento": "casa.vuota"})], [])
    )
    riga = _generate()[0]
    regola = regole_dominio.Regola(identificativo=riga["id"], nome=riga["nome"], trigger=riga["trigger"])

    assert regole_dominio.scatta_su_evento(regola, "casa.vuota", {}) is True
    assert regole_dominio.scatta_su_evento(regola, "casa.abitata", {}) is False
