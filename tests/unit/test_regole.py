"""Le regole: la casa smette di aspettare la domanda.

Il sistema era puramente reattivo. Le «modalita'» sono sequenze di azioni che
partono a comando, non automazioni. Mancavano i trigger.

Tre cose che questi test difendono, e che sono la differenza fra
un'automazione utile e una che si disattiva dopo tre giorni:

**Un trigger su soglia scatta quando si attraversa, non mentre si sta sotto.**
«Avvisami se scende sotto i 15» detto a una casa a 12 gradi non deve suonare
a ogni lettura del sensore. La differenza e' un avviso al giorno contro
trecento, e trecento avvisi al giorno diventano zero avvisi letti.

**La fascia oraria che scavalca la mezzanotte.** «Dalle 23 alle 6» e' la
finestra piu' usata in una casa — la notte — ed e' proprio quella che un
confronto ingenuo sbaglia sempre, perche' 23 non e' minore di 6.

**Un ciclo si ferma e si racconta.** Fermarlo e' il minimo; senza i nomi in
ordine, «una regola ha creato un ciclo» manda a rileggerle tutte.

Riferimento: issue #27.
"""

from __future__ import annotations

from datetime import datetime, time

import pytest

from shinra.domain import regole as dominio
from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento
from shinra.infra.db import depositi
from shinra.services.regole import MotoreRegole, _dalla_riga

# Mercoledi' 9 settembre 2026, ore 23:30. Di notte, feriale: la combinazione
# del criterio di accettazione della scheda.
NOTTE = datetime(2026, 9, 9, 23, 30)
GIORNO = datetime(2026, 9, 9, 14, 0)


def regola(**extra):
    base = {
        "identificativo": "reg_1",
        "nome": "Prova",
        "trigger": {},
        "condizioni": [],
        "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.ingresso"}],
    }
    base.update(extra)
    return dominio.Regola(**base)


# ======================================================= le soglie


@pytest.mark.parametrize(
    "precedente,attuale,atteso",
    [
        (16, 14, True),  # attraversa
        (15, 14, True),  # dal limite esatto
        (14, 13, False),  # era gia' sotto: non e' un attraversamento
        (14, 16, False),  # va nell'altro verso
        (16, 15, False),  # arriva al limite ma non lo passa
    ],
)
def test_attraversare_una_soglia_non_e_starci_sotto(precedente, attuale, atteso):
    """La differenza fra un avviso al giorno e trecento."""
    assert dominio.soglia_attraversata(dominio.ATTRAVERSA_SOTTO, precedente, attuale, 15) is atteso


@pytest.mark.parametrize("precedente", [None, "", "unavailable", "unknown"])
def test_senza_un_valore_precedente_non_si_dichiara_un_attraversamento(precedente):
    """La prima lettura dopo un riavvio, o un sensore tornato da
    `unavailable`: non si sa da dove veniva, e inventarlo vorrebbe dire
    accendere il riscaldamento a ogni riavvio di Home Assistant."""
    assert dominio.soglia_attraversata(dominio.ATTRAVERSA_SOTTO, precedente, 10, 15) is False


def test_sotto_invece_scatta_sempre():
    """Il rovescio: `sotto` esiste ed e' diverso, e va usato solo quando lo
    si vuole per davvero."""
    assert dominio.soglia_attraversata(dominio.SOTTO, 14, 13, 15) is True


def test_un_valore_non_numerico_non_scatta():
    assert dominio.soglia_attraversata(dominio.ATTRAVERSA_SOTTO, 16, "acceso", 15) is False


# ======================================================= le fasce orarie


@pytest.mark.parametrize(
    "ora,atteso", [(23, True), (0, True), (3, True), (6, True), (7, False), (12, False), (22, False)]
)
def test_la_fascia_che_scavalca_la_mezzanotte(ora, atteso):
    """«Dalle 23 alle 6» e' la finestra piu' usata in una casa, ed e' quella
    che un confronto ingenuo sbaglia sempre."""
    assert dominio._fra_le_ore(time(ora, 0), time(23, 0), time(6, 0)) is atteso


@pytest.mark.parametrize("ora,atteso", [(8, False), (9, True), (14, True), (18, True), (19, False)])
def test_una_fascia_normale_funziona_come_ci_si_aspetta(ora, atteso):
    assert dominio._fra_le_ore(time(ora, 0), time(9, 0), time(18, 0)) is atteso


# ======================================================= le condizioni


def test_perche_no_dice_quale_condizione_ha_fermato():
    """Una regola che non scatta mai e una rotta si somigliano troppo:
    senza il motivo, chi la scrive puo' solo indovinare."""
    r = regola(condizioni=[{"tipo": dominio.FRA_LE_ORE, "dalle": "23:00", "alle": "06:00"}])

    assert dominio.perche_no(r, GIORNO) is not None
    assert "23:00-06:00" in dominio.perche_no(r, GIORNO)
    assert dominio.perche_no(r, NOTTE) is None


def test_non_sapere_chi_c_e_non_e_sapere_che_non_c_e_nessuno():
    """Una regola che dipende dalla presenza non deve scattare al buio.

    Il motivo va verificato, non solo il fatto che ce ne sia uno: senza il
    controllo esplicito su `None`, la funzione risponde comunque «no» ma con
    la frase sbagliata — «in casa non c'e' nessuno» detto quando non lo si
    sa. Un controllo di mutazione l'ha mostrato: togliendo la guardia, la
    prima versione di questo test passava lo stesso.
    """
    vuota = regola(condizioni=[{"tipo": dominio.PRESENZA, "abitata": False}])

    assert dominio.perche_no(vuota, NOTTE, casa_abitata=False) is None
    assert "c'e' qualcuno" in dominio.perche_no(vuota, NOTTE, casa_abitata=True)
    assert "non so" in dominio.perche_no(vuota, NOTTE, casa_abitata=None)


def test_al_buio_non_si_afferma_il_contrario():
    """Il caso che la mutazione ha scoperto: con `abitata: True` e presenza
    ignota, senza la guardia la risposta sarebbe «in casa non c'e' nessuno»
    — un'affermazione, non un'ammissione di non sapere."""
    abitata = regola(condizioni=[{"tipo": dominio.PRESENZA, "abitata": True}])

    motivo = dominio.perche_no(abitata, NOTTE, casa_abitata=None)

    assert "non so" in motivo
    assert "non c'e' nessuno" not in motivo


def test_una_condizione_sullo_stato_di_un_entita():
    r = regola(condizioni=[{"tipo": dominio.STATO_ENTITA, "entity_id": "sun.sun", "stato": "below_horizon"}])

    assert dominio.perche_no(r, NOTTE, stati={"sun.sun": "below_horizon"}) is None
    assert "above_horizon" in dominio.perche_no(r, NOTTE, stati={"sun.sun": "above_horizon"})
    assert "non conosco" in dominio.perche_no(r, NOTTE, stati={})


def test_i_giorni_della_settimana():
    # 9 settembre 2026 e' un mercoledi': weekday() == 2
    r = regola(condizioni=[{"tipo": dominio.GIORNI, "giorni": [0, 1, 2, 3, 4]}])
    assert dominio.perche_no(r, GIORNO) is None

    solo_weekend = regola(condizioni=[{"tipo": dominio.GIORNI, "giorni": [5, 6]}])
    assert dominio.perche_no(solo_weekend, GIORNO) is not None


def test_senza_condizioni_non_c_e_niente_che_fermi():
    assert dominio.perche_no(regola(), GIORNO) is None


# ======================================================= gli inneschi


def test_un_trigger_su_evento_ristretto_a_un_entita():
    """«Quando si apre una porta» non deve scattare per una lampadina."""
    r = regola(
        trigger={"tipo": dominio.EVENTO, "evento": HA_STATO_CAMBIATO, "entity_id": "binary_sensor.porta"}
    )

    assert dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {"entity_id": "binary_sensor.porta"})
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {"entity_id": "light.salotto"})


def test_un_trigger_su_evento_ristretto_a_un_dominio():
    r = regola(trigger={"tipo": dominio.EVENTO, "evento": HA_STATO_CAMBIATO, "dominio": "lock"})

    assert dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {"dominio": "lock"})
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {"dominio": "light"})


def test_diventa_e_un_attraversamento_fatto_di_parole():
    """Si dichiara solo se lo stato e' cambiato davvero: una porta che
    resta aperta non si apre di nuovo a ogni aggiornamento."""
    r = regola(
        trigger={
            "tipo": dominio.STATO,
            "entity_id": "binary_sensor.porta",
            "confronto": dominio.DIVENTA,
            "valore": "on",
        }
    )

    assert dominio.scatta_su_evento(
        r, HA_STATO_CAMBIATO, {"entity_id": "binary_sensor.porta", "stato": "on", "stato_precedente": "off"}
    )
    assert not dominio.scatta_su_evento(
        r, HA_STATO_CAMBIATO, {"entity_id": "binary_sensor.porta", "stato": "on", "stato_precedente": "on"}
    )


# ======================================================= i cicli


def test_due_regole_che_si_innescano_a_vicenda_vengono_fermate():
    """Il criterio di accettazione della scheda."""
    with pytest.raises(dominio.Ciclo) as errore:
        dominio.verifica_catena(["reg_a", "reg_b"], "reg_a")

    assert errore.value.catena == ["reg_a", "reg_b", "reg_a"]


def test_il_ciclo_porta_con_se_la_catena():
    """«Una regola ha creato un ciclo» manda a rileggerle tutte: servono i
    nomi, in ordine."""
    with pytest.raises(dominio.Ciclo) as errore:
        dominio.verifica_catena(["a", "b", "c"], "a")

    assert "a -> b -> c -> a" in str(errore.value)


def test_anche_una_catena_troppo_lunga_e_un_ciclo():
    """Una catena legittima piu' lunga di tre e' quasi sempre un errore di
    chi l'ha scritta."""
    with pytest.raises(dominio.Ciclo):
        dominio.verifica_catena(["a", "b", "c"], "d")


def test_una_catena_corta_passa():
    assert dominio.verifica_catena(["a"], "b") == ["a", "b"]
    assert dominio.verifica_catena([], "a") == ["a"]


# ======================================================= gli orari


def test_una_regola_a_orario_sa_quando_scattera():
    r = regola(trigger={"tipo": dominio.ORARIO, "ora": "07:00"})

    prossimo = dominio.prossimo_scatto(r, NOTTE)

    assert (prossimo.day, prossimo.hour) == (10, 7)


def test_se_l_ora_e_gia_passata_si_va_a_domani():
    r = regola(trigger={"tipo": dominio.ORARIO, "ora": "07:00"})

    assert dominio.prossimo_scatto(r, GIORNO).day == 10


def test_una_regola_solo_feriale_salta_il_weekend():
    # sabato 12 settembre 2026
    sabato = datetime(2026, 9, 12, 9, 0)
    r = regola(trigger={"tipo": dominio.ORARIO, "ora": "07:00", "giorni": [0, 1, 2, 3, 4]})

    prossimo = dominio.prossimo_scatto(r, sabato)

    assert prossimo.weekday() == 0  # lunedi'


def test_una_regola_su_evento_non_ha_un_prossimo_scatto():
    r = regola(trigger={"tipo": dominio.EVENTO, "evento": HA_STATO_CAMBIATO})

    assert dominio.prossimo_scatto(r, GIORNO) is None


def test_il_tramonto_con_uno_scarto():
    r = regola(trigger={"tipo": dominio.TRAMONTO, "scarto_minuti": -30})
    tramonto = datetime(2026, 9, 9, 19, 45)

    assert dominio.prossimo_scatto(r, GIORNO, tramonto=tramonto).hour == 19
    assert dominio.prossimo_scatto(r, GIORNO, tramonto=tramonto).minute == 15


# ======================================================= il motore


@pytest.fixture
def casa(monkeypatch):
    """Home Assistant che annota, e uno scheduler che non parte."""
    chiamate: list[tuple[str, str, dict]] = []

    class FintoClient:
        async def call_service(self, dom, servizio, dati=None):
            chiamate.append((dom, servizio, dati or {}))
            return {"success": True}

        async def stati_correnti(self):
            return []

    class FintoScheduler:
        attivo = True

        def programma_azione(self, *a, **k):
            return True

        def annulla(self, *a, **k):
            return True

    from shinra.infra.scheduler import motore

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    monkeypatch.setattr(motore, "scheduler", FintoScheduler())
    return chiamate


async def test_se_la_porta_si_apre_dopo_le_23_accendi_l_ingresso(casa, monkeypatch):
    """Il criterio di accettazione della scheda, parola per parola."""
    chiamate = casa
    motore = MotoreRegole()

    motore.crea(
        {
            "nome": "Ingresso di notte",
            "trigger": {
                "tipo": dominio.STATO,
                "entity_id": "binary_sensor.porta",
                "confronto": dominio.DIVENTA,
                "valore": "on",
            },
            "condizioni": [{"tipo": dominio.FRA_LE_ORE, "dalle": "23:00", "alle": "06:00"}],
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.ingresso"}],
        }
    )
    monkeypatch.setattr("shinra.services.regole.datetime", _orologio(NOTTE))

    await motore._su_evento(
        Evento(
            tipo=HA_STATO_CAMBIATO,
            dati={"entity_id": "binary_sensor.porta", "stato": "on", "stato_precedente": "off"},
        )
    )

    assert ("light", "turn_on", {"entity_id": "light.ingresso"}) in chiamate


async def test_di_giorno_la_stessa_porta_non_accende_niente(casa, monkeypatch):
    """Il rovescio: senza, «accende sempre» passerebbe il test di sopra."""
    chiamate = casa
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Ingresso di notte",
            "trigger": {
                "tipo": dominio.STATO,
                "entity_id": "binary_sensor.porta",
                "confronto": dominio.DIVENTA,
                "valore": "on",
            },
            "condizioni": [{"tipo": dominio.FRA_LE_ORE, "dalle": "23:00", "alle": "06:00"}],
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.ingresso"}],
        }
    )
    monkeypatch.setattr("shinra.services.regole.datetime", _orologio(GIORNO))

    await motore._su_evento(
        Evento(
            tipo=HA_STATO_CAMBIATO,
            dati={"entity_id": "binary_sensor.porta", "stato": "on", "stato_precedente": "off"},
        )
    )

    assert chiamate == []


async def test_ogni_attivazione_e_tracciata_nel_registro(casa, monkeypatch):
    """Il quarto criterio della scheda. E' l'unica risposta possibile a
    «perche' si e' accesa la luce?»."""
    motore = MotoreRegole()
    voce = motore.crea(
        {
            "nome": "Prova",
            "trigger": {"tipo": dominio.ORARIO, "ora": "07:00"},
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.x"}],
        }
    )

    await motore.esegui(_dalla_riga(voce), motivo="prova")

    from shinra.services import registro

    tracciate = [v for v in registro.voci(limite=50) if v["azione"] == "regola.eseguita"]
    assert tracciate
    assert tracciate[0]["dettagli"]["nome"] == "Prova"


async def test_anche_il_rifiuto_e_registrato(casa, monkeypatch):
    """Una regola che non scatta mai e una rotta si somigliano troppo."""
    motore = MotoreRegole()
    voce = motore.crea(
        {
            "nome": "Solo di notte",
            "trigger": {"tipo": dominio.ORARIO, "ora": "07:00"},
            "condizioni": [{"tipo": dominio.FRA_LE_ORE, "dalle": "23:00", "alle": "06:00"}],
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.x"}],
        }
    )
    monkeypatch.setattr("shinra.services.regole.datetime", _orologio(GIORNO))

    esito = await motore.esegui(_dalla_riga(voce))

    from shinra.services import registro

    assert esito["eseguita"] is False
    saltate = [v for v in registro.voci(limite=50) if v["azione"] == "regola.saltata"]
    assert saltate
    assert "fascia" in saltate[0]["dettagli"]["motivo"]

    # E anche sulla regola, che e' il primo posto dove si guarda: un
    # controllo di mutazione ha mostrato che togliendo questa annotazione la
    # suite passava lo stesso, perche' l'unico test che la guardava usava la
    # strada dell'esecuzione riuscita.
    riletta = depositi.regole.per_id(voce["id"])
    assert riletta["ultimo_esito"].startswith("non eseguita:")
    assert riletta["ultimo_scatto"] is not None


async def test_l_ultimo_esito_si_legge_dalla_regola(casa):
    """E' la prima cosa che si guarda quando una regola «non funziona», e
    cercarla nel registro richiede di sapere gia' quando sarebbe dovuta
    scattare."""
    motore = MotoreRegole()
    voce = motore.crea(
        {
            "nome": "Prova",
            "trigger": {"tipo": dominio.ORARIO, "ora": "07:00"},
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.x"}],
        }
    )

    await motore.esegui(_dalla_riga(voce))

    riletta = depositi.regole.per_id(voce["id"])
    assert riletta["ultimo_esito"] == "1/1 azioni"
    assert riletta["ultimo_scatto"] is not None


async def test_un_ciclo_viene_fermato_e_raccontato(casa, monkeypatch):
    """Il terzo criterio della scheda: fermate **e segnalate**."""
    avvisi = []

    from shinra.services import notifiche as servizio_notifiche_modulo

    async def finto_avvisa(avviso, utente=None):
        avvisi.append(avviso)
        return {"inviate": 1, "per_canale": {}, "saltati": []}

    monkeypatch.setattr(servizio_notifiche_modulo.servizio_notifiche, "avvisa", finto_avvisa)

    motore = MotoreRegole()
    voce = motore.crea(
        {
            "nome": "Quella che si avvita",
            "trigger": {"tipo": dominio.ORARIO, "ora": "07:00"},
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.x"}],
        }
    )
    regola_letta = _dalla_riga(voce)

    esito = await motore.esegui(regola_letta, catena=[voce["id"]])

    assert esito["eseguita"] is False
    assert esito["ciclo"] == [voce["id"], voce["id"]]
    assert len(avvisi) == 1
    assert "Quella che si avvita" in avvisi[0].testo


async def test_una_regola_spenta_non_scatta(casa):
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Spenta",
            "attiva": False,
            "trigger": {"tipo": dominio.EVENTO, "evento": HA_STATO_CAMBIATO},
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.x"}],
        }
    )

    await motore._su_evento(Evento(tipo=HA_STATO_CAMBIATO, dati={"entity_id": "light.y"}))

    assert casa == []


async def test_cancellare_una_regola_toglie_anche_il_suo_job(casa):
    motore = MotoreRegole()
    voce = motore.crea(
        {
            "nome": "Da cancellare",
            "trigger": {"tipo": dominio.ORARIO, "ora": "07:00"},
            "azioni": [{"tipo": dominio.AZIONE_DISPOSITIVO, "entity_id": "light.x"}],
        }
    )

    assert motore.cancella(voce["id"]) is True
    assert depositi.regole.per_id(voce["id"]) is None


def _orologio(fisso: datetime):
    """Un `datetime` che dice sempre la stessa ora, per provare le fasce."""

    class Fermo(datetime):
        @classmethod
        def now(cls, tz=None):
            return fisso

    return Fermo
