"""Liste, calendario e scadenze: le tre entita' della scheda #25.

Il filo che le lega e' una decisione sola: **una lista ha un padrone solo.**
Dove Home Assistant ha una lista `todo` o un calendario `calendar`, si scrive
li' e si legge di li'; le tabelle di casa esistono per chi non ce li ha, e non
si specchiano mai. Una copia sincronizzata sarebbe due verita' che divergono
al primo conflitto, e una lista della spesa sbagliata e' peggio di nessuna
lista, perche' ci si va al supermercato.

Sui calendari c'e' un'asimmetria voluta: si **leggono** tutti, si **scrive**
solo su quello di casa. I calendari di Home Assistant sono di Google, di
iCloud, di chi li possiede: una casa che scrive nell'agenda di lavoro di
qualcuno fa un danno che non sa di fare.

Riferimento: issue #25.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from shinra.domain import calendario as cal_dominio
from shinra.domain import liste as liste_dominio
from shinra.domain import manutenzione as man_dominio
from shinra.infra.db import depositi
from shinra.skills import calendario, liste, manutenzione

OGGI = date(2026, 9, 9)


# ======================================================= LISTE


TODO_HA = [
    {
        "entity_id": "todo.lista_della_spesa",
        "state": "3",
        "attributes": {"friendly_name": "Lista della spesa"},
    },
    {"entity_id": "todo.cose_da_fare", "state": "1", "attributes": {"friendly_name": "Cose da fare"}},
    {"entity_id": "light.salotto", "state": "on", "attributes": {}},
]

VOCI_HA = {"todo.lista_della_spesa": {"items": [{"summary": "latte", "status": "needs_action"}]}}


@pytest.fixture
def con_todo(monkeypatch):
    """Una casa che ha le liste `todo` di Home Assistant."""
    chiamate: list[tuple[str, str, dict]] = []
    magazzino = {k: {"items": list(v["items"])} for k, v in VOCI_HA.items()}

    class FintoClient:
        async def stati_correnti(self):
            return list(TODO_HA)

        async def call_service(self, dominio, servizio, dati=None):
            chiamate.append((dominio, servizio, dati or {}))
            entita = (dati or {}).get("entity_id")
            voce = (dati or {}).get("item")
            if servizio == "add_item" and entita in magazzino:
                magazzino[entita]["items"].append({"summary": voce, "status": "needs_action"})
            if servizio == "remove_item" and entita in magazzino:
                magazzino[entita]["items"] = [i for i in magazzino[entita]["items"] if i["summary"] != voce]
            return {"success": True}

        async def chiama_con_risposta(self, dominio, servizio, dati=None):
            entita = (dati or {}).get("entity_id")
            return {"success": True, "risposta": {entita: magazzino.get(entita, {"items": []})}}

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    return chiamate


@pytest.fixture
def senza_ha(monkeypatch):
    """Una casa senza `todo`: le liste stanno sul database."""

    class Spoglia:
        async def stati_correnti(self):
            return [{"entity_id": "light.salotto", "state": "on", "attributes": {}}]

        async def call_service(self, dominio, servizio, dati=None):
            raise AssertionError("non deve chiamare Home Assistant: qui non ci sono liste todo")

        async def chiama_con_risposta(self, dominio, servizio, dati=None):
            raise AssertionError("non deve chiamare Home Assistant")

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: Spoglia())


async def test_aggiungi_il_latte_alla_lista_della_spesa(con_todo):
    """Il primo criterio di accettazione della scheda."""
    esito = await liste.aggiungi_a_lista("latte", "spesa")

    assert esito["success"] is True


async def test_con_le_todo_di_home_assistant_si_scrive_li(con_todo):
    """La decisione che governa tutto il modulo: una verita' sola."""
    await liste.aggiungi_a_lista("pane", "spesa")

    assert ("todo", "add_item", {"entity_id": "todo.lista_della_spesa", "item": "pane"}) in con_todo
    # E niente sul database di casa.
    assert depositi.liste.elenco() == []


async def test_senza_todo_la_lista_sta_in_casa(senza_ha):
    """Il rovescio: chi non ha `todo` deve comunque avere una lista. La
    fixture solleva se qualcuno prova a chiamare Home Assistant."""
    esito = await liste.aggiungi_a_lista("pane", "spesa")

    assert esito["success"] is True
    assert esito["dove"] == "casa"
    assert len(depositi.liste.elenco()) == 1


async def test_latte_pane_e_uova_sono_tre_voci(con_todo):
    """Chi detta la spesa non si ferma dopo il primo articolo, e una riga
    «latte pane e uova» si rilegge male al supermercato."""
    esito = await liste.aggiungi_a_lista("pane, uova e caffe", "spesa")

    assert sorted(esito["aggiunte"]) == ["caffe", "pane", "uova"]
    assert len([c for c in con_todo if c[1] == "add_item"]) == 3


async def test_non_si_aggiunge_due_volte_la_stessa_cosa(con_todo):
    """La lista ha gia' il latte: al supermercato due righe uguali si
    comprano due volte."""
    esito = await liste.aggiungi_a_lista("latte", "spesa")

    assert esito["aggiunte"] == []
    assert esito["gia_presenti"] == ["latte"]
    assert [c for c in con_todo if c[1] == "add_item"] == []


async def test_non_si_aggiunge_due_volte_nemmeno_in_casa(senza_ha):
    """Il ramo delle liste di casa ha la sua deduplica, e va provata a parte:
    un controllo di mutazione ha mostrato che togliendola i test passavano
    lo stesso, perche' guardavano tutti il ramo di Home Assistant."""
    await liste.aggiungi_a_lista("latte", "spesa")

    esito = await liste.aggiungi_a_lista("latte", "spesa")

    assert esito["aggiunte"] == []
    assert esito["gia_presenti"] == ["latte"]
    lista = depositi.liste.per_nome("spesa")
    assert len(depositi.voci_lista.della_lista(lista["id"])) == 1


async def test_leggere_e_togliere_da_una_lista_di_casa(senza_ha):
    await liste.aggiungi_a_lista("pane, uova", "spesa")

    letta = await liste.leggi_lista("spesa")
    assert sorted(letta["voci"]) == ["pane", "uova"]

    tolta = await liste.togli_da_lista("pane", "spesa")
    assert tolta["success"] is True

    di_nuovo = await liste.leggi_lista("spesa")
    assert di_nuovo["voci"] == ["uova"]


async def test_leggere_una_lista_di_home_assistant(con_todo):
    esito = await liste.leggi_lista("spesa")

    assert esito["success"] is True
    assert "latte" in esito["voci"]


async def test_togliere_una_voce(con_todo):
    esito = await liste.togli_da_lista("latte", "spesa")

    assert esito["success"] is True
    assert ("todo", "remove_item", {"entity_id": "todo.lista_della_spesa", "item": "latte"}) in con_todo


async def test_togliere_una_voce_che_non_c_e(con_todo):
    esito = await liste.togli_da_lista("caviale", "spesa")

    assert esito["success"] is False


@pytest.mark.parametrize(
    "detto,atteso",
    [
        ("la lista della spesa", "spesa"),
        ("spesa", "spesa"),
        ("supermercato", "spesa"),
        ("cosa manca", "spesa"),
        ("cose da fare", "cose da fare"),
        ("todo", "cose da fare"),
        ("", "spesa"),
        ("cantina", "cantina"),
    ],
)
def test_i_nomi_con_cui_si_chiama_una_lista(detto, atteso):
    assert liste_dominio.nome_canonico(detto) == atteso


def test_la_lista_giusta_fra_piu_todo():
    assert liste_dominio.scegli_entita("spesa", TODO_HA) == "todo.lista_della_spesa"
    assert liste_dominio.scegli_entita("cose da fare", TODO_HA) == "todo.cose_da_fare"


def test_senza_todo_non_si_sceglie_niente():
    """`None` e' il bivio su cui poggia il modulo: vuol dire «tienila in casa»."""
    assert liste_dominio.scegli_entita("spesa", []) is None
    assert liste_dominio.scegli_entita("spesa", [{"entity_id": "light.x"}]) is None


def test_con_una_todo_sola_e_quella():
    """Chi ne ha una la chiama come gli pare."""
    una = [{"entity_id": "todo.mia", "attributes": {"friendly_name": "Mia"}}]

    assert liste_dominio.scegli_entita("qualunque cosa", una) == "todo.mia"


@pytest.mark.parametrize(
    "detto,atteso",
    [
        ("latte", ["latte"]),
        ("latte, pane e uova", ["latte", "pane", "uova"]),
        ("pane e latte", ["pane", "latte"]),
        ("", []),
    ],
)
def test_separare_le_voci(detto, atteso):
    assert liste_dominio.separa_voci(detto) == atteso


# ======================================================= CALENDARIO


EVENTI_HA = [
    {
        "summary": "Dentista",
        "start": {"dateTime": "2026-09-09T15:30:00"},
        "end": {"dateTime": "2026-09-09T16:00:00"},
    },
    {"summary": "Compleanno di Marco", "start": {"date": "2026-09-09"}, "end": {"date": "2026-09-10"}},
    {
        "summary": "Vacanza",
        "start": {"date": "2026-09-05"},
        "end": {"date": "2026-09-15"},
        "location": "Grecia",
    },
]


def test_una_giornata_intera_non_e_un_evento_delle_zero_zero():
    """Il difetto che questo test impedisce: letta come un orario, una
    giornata intera risulta gia' passata per tutte le ore in cui accade."""
    eventi = cal_dominio.da_home_assistant(EVENTI_HA)
    compleanno = next(e for e in eventi if "Compleanno" in e.titolo)

    assert compleanno.tutto_il_giorno is True
    assert "tutto il giorno" in cal_dominio.descrivi(compleanno)


def test_un_evento_con_ora_conserva_l_ora():
    eventi = cal_dominio.da_home_assistant(EVENTI_HA)
    dentista = next(e for e in eventi if e.titolo == "Dentista")

    assert dentista.tutto_il_giorno is False
    assert "15:30" in cal_dominio.descrivi(dentista)


def test_una_vacanza_cominciata_prima_e_un_impegno_anche_oggi():
    """Un calendario che mostra la vacanza solo il giorno di partenza non
    risponde alla domanda «cosa ho oggi»."""
    eventi = cal_dominio.da_home_assistant(EVENTI_HA)

    del_giorno = cal_dominio.del_giorno(eventi, OGGI)

    assert any(e.titolo == "Vacanza" for e in del_giorno)


def test_una_giornata_intera_non_sborda_nel_giorno_dopo():
    """Home Assistant chiude le giornate intere alla mezzanotte del giorno
    dopo: senza correzione il compleanno comparirebbe anche il 10."""
    eventi = cal_dominio.da_home_assistant(EVENTI_HA)

    domani = cal_dominio.del_giorno(eventi, date(2026, 9, 10))

    assert not any("Compleanno" in e.titolo for e in domani)
    assert any(e.titolo == "Vacanza" for e in domani)


def test_prima_le_giornate_intere_poi_gli_orari():
    """Chi chiede «cosa ho oggi» vuole sapere prima che e' un compleanno, e
    poi che alle 15 c'e' il dentista."""
    eventi = cal_dominio.del_giorno(cal_dominio.da_home_assistant(EVENTI_HA), OGGI)

    assert eventi[0].tutto_il_giorno is True
    assert eventi[-1].titolo == "Dentista"


def test_senza_impegni_lo_dice():
    assert "Non hai impegni" in cal_dominio.riassumi([], "oggi")


def test_il_luogo_entra_nella_frase():
    eventi = cal_dominio.da_home_assistant(EVENTI_HA)
    vacanza = next(e for e in eventi if e.titolo == "Vacanza")

    assert "Grecia" in cal_dominio.descrivi(vacanza)


@pytest.fixture
def con_calendario(monkeypatch):
    class FintoClient:
        async def stati_correnti(self):
            return []

        async def leggi(self, percorso, parametri=None):
            if percorso == "calendars":
                return [{"entity_id": "calendar.casa", "name": "Casa"}]
            if percorso.startswith("calendars/"):
                return list(EVENTI_HA)
            return None

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())


async def test_cosa_ho_oggi_elenca_gli_impegni_reali(con_calendario, monkeypatch):
    """Il secondo criterio di accettazione della scheda."""
    monkeypatch.setattr(calendario, "_giorno_detto", lambda d: (OGGI, "oggi"))

    esito = await calendario.impegni("oggi")

    assert esito["success"] is True
    titoli = [i["titolo"] for i in esito["impegni"]]
    assert "Dentista" in titoli
    assert "Compleanno di Marco" in titoli


async def test_gli_impegni_di_casa_si_sommano_a_quelli_di_home_assistant(con_calendario, monkeypatch):
    """Chi ha Google e in piu' segna qualcosa qui deve vedere tutte e due le
    cose."""
    monkeypatch.setattr(calendario, "_giorno_detto", lambda d: (OGGI, "oggi"))
    depositi.eventi_calendario.aggiungi(
        {
            "id": "evt_1",
            "titolo": "Riunione condominio",
            "inizio": datetime(2026, 9, 9, 21, 0),
            "fine": None,
            "tutto_il_giorno": False,
            "luogo": "",
            "autore": "alessio",
        }
    )

    esito = await calendario.impegni("oggi")

    titoli = [i["titolo"] for i in esito["impegni"]]
    assert "Riunione condominio" in titoli
    assert "Dentista" in titoli


async def test_aggiungere_un_impegno_non_tocca_i_calendari_di_home_assistant(con_calendario):
    """Quelli sono di Google, di iCloud, di chi li possiede: una casa che
    scrive nell'agenda di lavoro di qualcuno fa un danno che non sa di fare."""
    esito = await calendario.aggiungi_impegno("cena con Marco", "domani alle 20")

    assert esito["success"] is True
    righe = depositi.eventi_calendario.elenco()
    assert len(righe) == 1
    assert righe[0]["autore"] is None or isinstance(righe[0]["autore"], str)


async def test_un_impegno_senza_quando_viene_chiesto(con_calendario):
    esito = await calendario.aggiungi_impegno("cena con Marco", "prima o poi")

    assert esito["success"] is False
    assert esito["serve"] == "quando"
    assert depositi.eventi_calendario.elenco() == []


# ======================================================= MANUTENZIONE


def test_la_prossima_si_conta_da_quando_e_stata_fatta():
    """Contandola dalla data prevista, ogni ritardo si accumulerebbe: un
    cambio filtri fatto con due mesi di ritardo terrebbe il calendario
    indietro per sempre."""
    prevista = date(2026, 3, 1)
    fatta_in_ritardo = date(2026, 5, 1)

    prossima = man_dominio.prossima_dopo(fatta_in_ritardo, 6, man_dominio.MESI)

    assert prossima == date(2026, 11, 1)
    assert prossima != man_dominio.prossima_dopo(prevista, 6, man_dominio.MESI)


@pytest.mark.parametrize(
    "partenza,ogni,unita,attesa",
    [
        (date(2026, 1, 31), 1, man_dominio.MESI, date(2026, 2, 28)),
        (date(2026, 1, 31), 1, man_dominio.ANNI, date(2027, 1, 31)),
        (date(2028, 2, 29), 1, man_dominio.ANNI, date(2029, 2, 28)),
        (date(2026, 1, 31), 90, man_dominio.GIORNI, date(2026, 5, 1)),
        (date(2026, 12, 15), 2, man_dominio.MESI, date(2027, 2, 15)),
    ],
)
def test_le_ricorrenze_non_scivolano(partenza, ogni, unita, attesa):
    """Il 31 gennaio piu' un mese e' il 28 febbraio, non il 3 marzo: una
    scadenza che scivola di qualche giorno a ogni rinnovo, dopo dieci anni e'
    in un altro mese."""
    assert man_dominio.prossima_dopo(partenza, ogni, unita) == attesa


def test_una_garanzia_non_torna():
    """Riproporla ogni due anni sarebbe una bugia."""
    assert man_dominio.prossima_dopo(date(2026, 1, 1), 0, man_dominio.ANNI) is None


def test_scadute_e_in_arrivo_sono_due_cose_diverse():
    """«Il bollo scade fra tre giorni» e «il bollo e' scaduto due mesi fa»
    richiedono reazioni diverse."""
    scadenze = [
        man_dominio.Scadenza("a", "Bollo", OGGI - timedelta(days=60)),
        man_dominio.Scadenza("b", "Filtri", OGGI + timedelta(days=3)),
        man_dominio.Scadenza("c", "Revisione", OGGI + timedelta(days=200)),
    ]

    scadute, in_arrivo = man_dominio.da_segnalare(scadenze, OGGI)

    assert [s.titolo for s in scadute] == ["Bollo"]
    assert [s.titolo for s in in_arrivo] == ["Filtri"]


def test_una_scadenza_passata_resta_passata():
    """Non si sposta in avanti da sola per far tornare i conti."""
    vecchia = man_dominio.Scadenza("a", "Bollo", OGGI - timedelta(days=60))

    assert vecchia.scaduta(OGGI)
    assert "era scaduta 60 giorni fa" in man_dominio.descrivi(vecchia, OGGI)


def test_il_preavviso_e_per_riga():
    """Un bollo si annuncia con piu' anticipo di un filtro."""
    presto = man_dominio.Scadenza("a", "Bollo", OGGI + timedelta(days=30), preavviso=60)
    tardi = man_dominio.Scadenza("b", "Filtri", OGGI + timedelta(days=30), preavviso=7)

    assert presto.in_arrivo(OGGI)
    assert not tardi.in_arrivo(OGGI)


async def test_segnare_una_scadenza_e_ritrovarla():
    await manutenzione.aggiungi_scadenza("cambio filtri caldaia", "il 15", ogni=6, unita="mesi")

    esito = await manutenzione.scadenze_in_arrivo(giorni=30)

    assert esito["success"] is True
    assert any("filtri" in t.lower() for t in esito.get("in_arrivo", []) + esito.get("scadute", []))


async def test_una_scadenza_senza_data_viene_chiesta():
    esito = await manutenzione.aggiungi_scadenza("cambio filtri", "prima o poi")

    assert esito["success"] is False
    assert esito["serve"] == "quando"
    assert depositi.scadenze.elenco() == []


async def test_segnarla_fatta_sposta_la_prossima():
    await manutenzione.aggiungi_scadenza("cambio filtri", "il 15", ogni=6, unita="mesi")

    esito = await manutenzione.segna_fatta("filtri")

    assert esito["success"] is True
    attesa = man_dominio.prossima_dopo(date.today(), 6, man_dominio.MESI)
    assert esito["prossima"] == attesa.isoformat()


async def test_una_scadenza_che_non_torna_sparisce_quando_e_fatta():
    await manutenzione.aggiungi_scadenza("garanzia lavatrice", "il 20", ogni=0)

    esito = await manutenzione.segna_fatta("garanzia")

    assert esito["success"] is True
    assert depositi.scadenze.elenco() == []


async def test_senza_scadenze_lo_dice():
    esito = await manutenzione.scadenze_in_arrivo()

    assert esito["success"] is True
    assert esito["scadenze"] == []


# ---------------------------------- il criterio: un promemoria che scatta


@pytest.fixture
def scheduler_finto(monkeypatch):
    from shinra.infra.scheduler import motore

    programmati: dict[str, tuple] = {}

    class Finto:
        attivo = True

        def programma_promemoria(self, identificativo, testo, quando_iso, utente):
            programmati[identificativo] = (testo, quando_iso, utente)
            return True

        def annulla_promemoria(self, identificativo):
            programmati.pop(identificativo, None)
            return True

        def annulla(self, identificativo):
            return True

        def programma_periodico(self, identificativo, funzione, ore):
            return True

    monkeypatch.setattr(motore, "scheduler", Finto())
    return programmati


async def test_una_scadenza_genera_un_promemoria_che_scatta(scheduler_finto):
    """Il terzo criterio di accettazione della scheda, e quello che rende
    utile tutta la funzione: una scadenza in un elenco che nessuno apre e'
    una scadenza dimenticata. E' stato possibile prometterlo solo dopo la
    riparazione dei promemoria (#92)."""
    from shinra.services.manutenzione import servizio_manutenzione
    from shinra.skills import reminders

    await manutenzione.aggiungi_scadenza("cambio filtri", "il 15", ogni=6, unita="mesi")

    creati = servizio_manutenzione.controlla(oggi=date(2026, 9, 12))

    assert creati == 1
    assert reminders._promemoria_in_attesa() == 1
    assert len(scheduler_finto) == 1


async def test_non_si_crea_un_promemoria_a_ogni_giro(scheduler_finto):
    """Un bollo con sette giorni di preavviso produrrebbe sette sveglie."""
    from shinra.services.manutenzione import servizio_manutenzione

    await manutenzione.aggiungi_scadenza("cambio filtri", "il 15", ogni=6, unita="mesi")

    primo = servizio_manutenzione.controlla(oggi=date(2026, 9, 12))
    secondo = servizio_manutenzione.controlla(oggi=date(2026, 9, 13))

    assert (primo, secondo) == (1, 0)


async def test_una_scadenza_lontana_non_produce_niente(scheduler_finto):
    from shinra.services.manutenzione import servizio_manutenzione

    await manutenzione.aggiungi_scadenza("revisione auto", "il 15", ogni=2, unita="anni")

    assert servizio_manutenzione.controlla(oggi=date(2026, 1, 1)) == 0


def test_una_scadenza_passata_si_annuncia_subito():
    """Un promemoria programmato nel passato non suona mai: e' il modo piu'
    silenzioso di perdere un bollo scaduto."""
    from shinra.services.manutenzione import _quando_avvisare

    vecchia = man_dominio.Scadenza("a", "Bollo", OGGI - timedelta(days=60))

    quando = _quando_avvisare(vecchia, OGGI)

    assert quando > datetime.now()
