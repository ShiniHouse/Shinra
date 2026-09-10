"""Chi ha parlato, e cosa comporta non saperlo.

Il buco che questi test chiudono era piu' largo di come l'ADR 0004 lo
dichiarava. La frase scritta li' — «chiunque si rivolga a un Echo agisce con
l'identita' configurata nella sessione» — descriveva un problema di identita'
sbagliata. Misurandolo si e' visto che era un problema di identita' **assente**:

    attore_nel_contesto      = None
    profilo_corrente         = None
    puo_aprire_serrature     = True

`ha_permesso(None, ...)` concede tutto, perche' `None` vuol dire «nessuna
identita' in gioco» — l'autenticazione spenta, lo scheduler che annuncia un
promemoria. Il canale vocale non impostava mai l'attore, quindi finiva li'
dentro: **a voce nessun permesso e' mai stato verificato.** A trattenere
qualcosa restavano due divieti scritti a mano nelle capacita' — niente
serrature da Alexa, conferma in piu' per l'allarme — e nient'altro.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

import pytest

from shinra.domain import voce as dominio
from shinra.infra.db import depositi
from shinra.services import permessi, registro
from shinra.services.voci import servizio_voci


@pytest.fixture(autouse=True)
def famiglia():
    permessi.assicura_ruoli_predefiniti()
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "thomas", "name": "Thomas", "role": "teen"},
        ]
    )
    registro.apri_contesto(canale="alexa")
    yield


def _richiesta(person_id: str | None = None) -> dict:
    dati: dict = {
        "request": {"type": "IntentRequest", "intent": {"name": "GeneralQueryIntent", "slots": {}}},
        "session": {"attributes": {}},
        "context": {"System": {"user": {"userId": "amzn1.account.DICASA"}}},
    }
    if person_id:
        dati["context"]["System"]["person"] = {"personId": person_id}
    return dati


# ------------------------------------------------------------- il dominio


def test_l_identificativo_si_legge_da_context_system_person():
    assert dominio.persona_dalla_richiesta(_richiesta("amzn1.person.ALESSIO")) == "amzn1.person.ALESSIO"


def test_senza_profili_vocali_non_c_e_identificativo():
    """E' la condizione normale, non un errore: i profili vocali vanno
    configurati, e in molte case non lo sono."""
    assert dominio.persona_dalla_richiesta(_richiesta()) is None


def test_l_account_di_casa_non_e_l_identita_di_nessuno():
    """`context.System.user.userId` e' lo stesso per tutti quelli che vivono
    qui. Usarlo come identita' ricreerebbe esattamente il problema."""
    dati = _richiesta()
    assert "amzn1.account.DICASA" not in str(dominio.persona_dalla_richiesta(dati) or "")


def test_una_voce_associata_si_risolve_nel_profilo():
    identita = dominio.risolvi("v1", {"v1": "alessio"}, {"alessio": {}})

    assert identita.riconosciuta
    assert identita.user_id == "alessio"
    assert identita.motivo == dominio.RICONOSCIUTA


def test_una_voce_sentita_ma_non_attribuita_non_e_riconosciuta():
    """Sapere che «e' sempre la stessa voce» non basta: i permessi stanno sui
    ruoli, e un ruolo ce l'hanno i profili."""
    identita = dominio.risolvi("v1", {"v1": None}, {"alessio": {}})

    assert not identita.riconosciuta
    assert identita.motivo == dominio.VOCE_NON_ASSOCIATA


def test_una_voce_mai_sentita_non_e_riconosciuta():
    identita = dominio.risolvi("v9", {"v1": "alessio"}, {"alessio": {}})

    assert not identita.riconosciuta
    assert identita.motivo == dominio.VOCE_NON_ASSOCIATA


def test_cancellare_un_profilo_non_restituisce_i_permessi_alla_sua_voce():
    """Senza il controllo, l'attore verrebbe impostato su un identificativo
    che non esiste piu'; `profilo_corrente()` non troverebbe nessuno, e
    cancellare un profilo riaprirebbe il buco."""
    identita = dominio.risolvi("v1", {"v1": "sparito"}, {"alessio": {}})

    assert not identita.riconosciuta
    assert identita.motivo == dominio.PROFILO_SPARITO


@pytest.mark.parametrize(
    "motivo",
    [dominio.SENZA_PROFILI_VOCALI, dominio.VOCE_NON_ASSOCIATA, dominio.PROFILO_SPARITO],
)
def test_ogni_rifiuto_dice_cosa_fare(motivo):
    """Un rifiuto che non spiega si ripete."""
    detto = dominio.spiega(dominio.Identita(motivo=motivo), "apro la porta")

    assert "impostazioni" in detto


# ------------------------------------------------- il servizio e il contesto


def test_una_voce_riconosciuta_diventa_l_attore_della_richiesta():
    depositi.voci_sentite.segna_passaggio("v1")
    depositi.voci_sentite.associa("v1", "alessio")

    identita = servizio_voci.identifica(_richiesta("v1"))
    servizio_voci.applica(identita)

    assert registro.contesto().attore == "alessio"
    assert permessi.profilo_corrente().id == "alessio"
    assert permessi.ha_permesso(permessi.profilo_corrente(), permessi.COMANDA_SICUREZZA)


def test_una_voce_sconosciuta_ottiene_i_permessi_dell_ospite_non_quelli_di_nessuno():
    """Il cuore della issue: «non so chi sei» non e' «non c'e' nessuno»."""
    identita = servizio_voci.identifica(_richiesta("v-mai-vista"))
    servizio_voci.applica(identita)

    profilo = permessi.profilo_corrente()

    assert profilo is not None, "None vorrebbe dire «nessuna identita'», cioe' tutto concesso"
    assert profilo.role == "guest"
    assert not permessi.ha_permesso(profilo, permessi.COMANDA_SICUREZZA)
    assert not permessi.ha_permesso(profilo, permessi.COMANDA_DISPOSITIVI)


def test_senza_profili_vocali_valgono_lo_stesso_i_permessi_minimi():
    servizio_voci.applica(servizio_voci.identifica(_richiesta()))

    assert not permessi.ha_permesso(permessi.profilo_corrente(), permessi.COMANDA_SICUREZZA)


def test_una_voce_non_riconosciuta_non_eredita_l_attore_gia_nel_contesto():
    """Il middleware apre il contesto leggendo il cookie di sessione su *ogni*
    richiesta, compresa quella di Alexa. Se la voce non riconosciuta tenesse
    quell'attore, parlerebbe con i permessi di quella persona."""
    registro.apri_contesto(attore="alessio", canale="alexa")

    servizio_voci.applica(servizio_voci.identifica(_richiesta("v-mai-vista")))

    assert registro.contesto().attore is None
    assert permessi.profilo_corrente().role == "guest"


def test_il_ruolo_di_ricaduta_si_configura(monkeypatch):
    """Chi si e' costruito un «Ospite fine settimana» piu' stretto puo' usarlo."""
    from shinra.config.settings import settings

    depositi.ruoli.aggiungi(
        {"id": "muto", "nome": "Muto", "descrizione": "Niente.", "permessi": [], "predefinito": False}
    )
    monkeypatch.setattr(settings.alexa, "ruolo_voce_sconosciuta", "muto")

    servizio_voci.applica(servizio_voci.identifica(_richiesta("v-mai-vista")))

    assert permessi.profilo_corrente().role == "muto"
    assert not permessi.ha_permesso(permessi.profilo_corrente(), permessi.LEGGI_CONOSCENZA)


def test_un_ruolo_di_ricaduta_inesistente_non_concede_niente(monkeypatch):
    """La direzione giusta in cui sbagliare."""
    from shinra.config.settings import settings

    monkeypatch.setattr(settings.alexa, "ruolo_voce_sconosciuta", "questo-ruolo-non-esiste")

    servizio_voci.applica(servizio_voci.identifica(_richiesta("v-mai-vista")))

    for permesso in permessi.TUTTI:
        assert not permessi.ha_permesso(permessi.profilo_corrente(), permesso)


def test_un_attore_senza_profilo_non_vale_come_nessun_attore():
    """Succede cancellando una persona mentre qualcosa la nomina ancora.
    Prima diventava `None`, cioe' tutti i permessi."""
    registro.apri_contesto(attore="fantasma", canale="web")

    profilo = permessi.profilo_corrente()

    assert profilo is not None
    assert not permessi.ha_permesso(profilo, permessi.COMANDA_SICUREZZA)


def test_nessuna_identita_in_gioco_resta_permessa():
    """Lo scheduler che annuncia un promemoria non ha un ruolo, e negargli i
    permessi che l'utente gli ha dato creando il promemoria sarebbe assurdo."""
    registro.apri_contesto(attore=None, canale="")

    assert permessi.profilo_corrente() is None
    assert permessi.ha_permesso(None, permessi.COMANDA_SICUREZZA)


# ------------------------------------------------------------- l'archivio


def test_una_voce_sconosciuta_viene_annotata_per_poterla_associare():
    """Altrimenti associarla vorrebbe dire copiare a mano un identificativo
    opaco letto in un log."""
    servizio_voci.identifica(_richiesta("v-nuova"))
    servizio_voci.identifica(_richiesta("v-nuova"))

    riga = depositi.voci_sentite.per_id("v-nuova")

    assert riga is not None
    assert riga["user_id"] is None
    assert riga["quante_volte"] == 2


def test_annotare_il_passaggio_non_associa_niente():
    servizio_voci.identifica(_richiesta("v-nuova"))
    servizio_voci.applica(servizio_voci.identifica(_richiesta("v-nuova")))

    assert permessi.profilo_corrente().role == "guest"


def test_associare_a_un_profilo_inesistente_viene_rifiutato():
    """Un errore di battitura non deve produrre un'associazione che sembra
    valida."""
    depositi.voci_sentite.segna_passaggio("v1")

    with pytest.raises(ValueError):
        servizio_voci.associa("v1", "nessuno")

    assert depositi.voci_sentite.per_id("v1")["user_id"] is None


def test_dissociare_riporta_la_voce_a_sconosciuta():
    depositi.voci_sentite.segna_passaggio("v1")
    servizio_voci.associa("v1", "alessio")

    servizio_voci.associa("v1", None)

    servizio_voci.applica(servizio_voci.identifica(_richiesta("v1")))
    assert permessi.profilo_corrente().role == "guest"


def test_cancellare_una_persona_libera_le_sue_voci():
    """Una riga che indica il vuoto e' una riga che prima o poi qualcuno
    legge come valida."""
    from shinra.services.user_manager import user_manager

    depositi.voci_sentite.segna_passaggio("v1")
    servizio_voci.associa("v1", "thomas")

    user_manager.delete_user("thomas")

    assert depositi.voci_sentite.per_id("v1")["user_id"] is None


def test_l_elenco_mostra_il_nome_di_chi_e_associato():
    depositi.voci_sentite.segna_passaggio("v1")
    depositi.voci_sentite.segna_passaggio("v2")
    servizio_voci.associa("v1", "alessio")

    per_id = {r["person_id"]: r for r in servizio_voci.elenco()}

    assert per_id["v1"]["nome_profilo"] == "Alessio"
    assert per_id["v2"]["nome_profilo"] is None
