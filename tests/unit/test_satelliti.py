"""Piu' orecchie in casa, una bocca sola che risponde.

Il test che conta di piu' e' `test_due_satelliti_che_sentono_la_stessa_frase`:
e' il criterio di accettazione della scheda, ed e' anche la cosa che non si
puo' provare in casa senza due dispositivi accesi insieme — cioe' quella che
verrebbe scoperta rotta nel momento peggiore.

Il secondo e' `test_lo_stesso_satellite_che_ripete_non_e_un_eco`: se lo si
scambiasse per un'eco, dire due volte «accendi la luce» funzionerebbe una
volta sola, e la seconda richiesta sparirebbe senza un errore.

Riferimento: issue #33.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shinra.domain import satelliti as dominio

ADESSO = datetime(2026, 9, 10, 21, 0, 0)


def _a(satellite: str, frase: str = "accendi la luce", ritardo: float = 0.0):
    return dominio.Ascolto(
        satellite=satellite,
        frase=frase,
        quando=ADESSO + timedelta(seconds=ritardo),
    )


# ============================================================ chi risponde


def test_un_satellite_solo_risponde_lui():
    assert dominio.deve_rispondere(_a("cucina"), []) is True


def test_due_satelliti_che_sentono_la_stessa_frase():
    """Il criterio della scheda: non rispondono entrambi.

    Due telefoni sullo stesso tavolo sentono la stessa cosa. Se rispondessero
    in due, la casa direbbe tutto due volte e accenderebbe la luce due volte
    — che per una luce non si nota e per una serranda si'.
    """
    primo = _a("cucina", ritardo=0.0)

    assert dominio.deve_rispondere(primo, []) is True
    assert dominio.deve_rispondere(_a("salotto", ritardo=0.3), [primo]) is False


def test_un_ascolto_senza_frase_non_risponde_e_non_zittisce():
    """Un satellite che manda una trascrizione vuota non ha sentito niente:
    farlo valere vorrebbe dire zittire quello che ha sentito davvero."""
    vuoto = _a("cucina", frase="   ")

    assert dominio.deve_rispondere(vuoto, []) is False
    assert dominio.deve_rispondere(_a("salotto", ritardo=0.2), [vuoto]) is True


def test_una_frase_diversa_non_e_un_eco():
    """Chi ha sentito un'altra cosa non deve essere zittito."""
    primo = _a("cucina", "accendi la luce")

    assert dominio.deve_rispondere(_a("salotto", "che ora e", ritardo=0.2), [primo]) is True


def test_una_frase_uguale_ma_tardiva_e_una_seconda_richiesta():
    primo = _a("cucina", ritardo=0.0)

    assert dominio.deve_rispondere(_a("salotto", ritardo=30.0), [primo]) is True


def test_gli_ascolti_vecchi_si_dimenticano():
    """Senza, l'elenco cresce per sempre e con esso il costo di ogni frase
    detta in casa."""
    vecchio = _a("cucina", ritardo=-60.0)
    fresco = _a("salotto", ritardo=-1.0)

    restano = dominio.solo_recenti([vecchio, fresco], ADESSO)

    assert [a.satellite for a in restano] == ["salotto"]


def test_una_frase_arrivata_troppo_dopo_non_e_un_eco():
    """Allargare la finestra vorrebbe dire scambiare per un'eco due richieste
    dette di seguito, e la seconda andrebbe persa: molto peggio che
    rispondere due volte."""
    tardi = _a("salotto", ritardo=30.0)

    assert dominio.e_la_stessa_frase(_a("cucina"), tardi) is False


def test_lo_stesso_satellite_che_ripete_non_e_un_eco():
    """Se qualcuno dice due volte «accendi la luce» allo stesso telefono,
    sono due richieste, non una sentita due volte."""
    assert dominio.e_la_stessa_frase(_a("cucina", ritardo=0.0), _a("cucina", ritardo=0.5)) is False


def test_la_punteggiatura_non_fa_due_frasi_di_una():
    """Due trascrizioni della stessa frase possono differire per una virgola,
    e una virgola non e' una richiesta diversa."""
    uno = _a("cucina", "Accendi la luce!")
    altro = _a("salotto", "accendi la luce", ritardo=0.2)

    assert dominio.e_la_stessa_frase(uno, altro) is True


# ======================================================= chi c'e' ancora


def test_un_satellite_che_si_e_fatto_sentire_e_presente():
    s = dominio.Satellite("s1", "Telefono", "Cucina", visto_il=ADESSO - timedelta(seconds=30))

    assert s.presente(ADESSO) is True


def test_un_satellite_che_tace_da_troppo_non_c_e_piu():
    """Chi chiude la scheda del browser non si disconnette: smette e basta."""
    s = dominio.Satellite("s1", "Telefono", "Cucina", visto_il=ADESSO - timedelta(hours=2))

    assert s.presente(ADESSO) is False


def test_un_satellite_mai_visto_non_e_presente():
    assert dominio.Satellite("s1").presente(ADESSO) is False


def test_l_elenco_dei_presenti_esclude_chi_tace():
    satelliti = [
        dominio.Satellite("vivo", stanza="Cucina", visto_il=ADESSO),
        dominio.Satellite("morto", stanza="Salotto", visto_il=ADESSO - timedelta(hours=1)),
    ]

    assert [s.identificativo for s in dominio.presenti(satelliti, ADESSO)] == ["vivo"]


def test_l_elenco_non_si_riordina_da_solo():
    """Finisce sotto gli occhi di qualcuno: un elenco che cambia ordine a
    ogni sguardo non si riesce a leggere."""
    satelliti = [
        dominio.Satellite("b", stanza="Salotto", visto_il=ADESSO),
        dominio.Satellite("a", stanza="Cucina", visto_il=ADESSO - timedelta(seconds=1)),
    ]

    ordinati = [s.identificativo for s in dominio.presenti(satelliti, ADESSO)]

    assert ordinati == ["a", "b"]


# ========================================================== da dove parla


def test_la_stanza_di_un_satellite_conosciuto():
    satelliti = [dominio.Satellite("s1", stanza="Cucina", visto_il=ADESSO)]

    assert dominio.stanza_di(satelliti, "s1") == "Cucina"


def test_di_un_satellite_sconosciuto_non_si_inventa_la_stanza():
    """Attribuire un comando alla stanza sbagliata e' peggio che non
    attribuirlo a nessuna: accende la luce di qualcun altro."""
    satelliti = [dominio.Satellite("s1", stanza="Cucina", visto_il=ADESSO)]

    assert dominio.stanza_di(satelliti, "mai_visto") == ""


@pytest.mark.parametrize("soglia,atteso", [(60, False), (60 * 60, True)])
def test_la_soglia_di_silenzio_si_puo_cambiare(soglia, atteso):
    """Due minuti di silenzio: troppi per una soglia di un minuto, pochi per
    una di un'ora."""
    s = dominio.Satellite("s1", visto_il=ADESSO - timedelta(seconds=120))

    assert s.presente(ADESSO, timedelta(seconds=soglia)) is atteso
