"""«Accendi la luce» — ma quale, e dove.

Il test che conta piu' di tutti e'
`test_un_riferimento_ambiguo_non_sceglie_a_caso`. Prima di questo modulo la
risoluzione era `riferimento in nome`, quindi «luce» corrispondeva a «luce
cucina», «luce salotto» e «luce bagno» insieme, e vinceva quella che
l'archivio restituiva per prima. Nessun avviso: chi ascoltava credeva di
essere stato capito, e la volta dopo ripeteva la stessa frase aspettandosi lo
stesso risultato.

Il secondo e' `test_la_stanza_di_chi_parla_scioglie_l_ambiguita`, che e' tutto
il senso di avere un punto di ascolto per stanza.

Il terzo e' `test_una_stanza_che_non_c_entra_non_impedisce_il_comando`: la
stanza deve restringere, non recintare. Un satellite in corridoio che chiede
la luce del salotto deve poterla accendere.

Riferimento: issue #33.
"""

from __future__ import annotations

import pytest

from shinra.domain import stanze as dominio


def _d(entity_id: str, alias: str = "", stanza: str = "") -> dominio.Dispositivo:
    return dominio.Dispositivo(entity_id=entity_id, alias=alias, stanza=stanza)


TRE_LUCI = [
    _d("light.cucina", "luce cucina", "Cucina"),
    _d("light.salotto", "luce salotto", "Salotto"),
    _d("light.bagno", "luce bagno", "Bagno"),
]


# ============================================================ il caso semplice


def test_un_entity_id_scritto_per_esteso_e_gia_la_risposta():
    esito = dominio.risolvi("light.salotto", TRE_LUCI)

    assert esito.certo
    assert esito.entity_id == "light.salotto"


def test_un_entity_id_non_ha_bisogno_di_essere_conosciuto():
    """Chi lo scrive per esteso sa quello che vuole, e la verifica successiva
    dira' se esiste davvero."""
    esito = dominio.risolvi("switch.qualcosa_di_nuovo", TRE_LUCI)

    assert esito.entity_id == "switch.qualcosa_di_nuovo"


def test_un_alias_che_corrisponde_a_uno_solo():
    esito = dominio.risolvi("luce cucina", TRE_LUCI)

    assert esito.entity_id == "light.cucina"


def test_le_parole_di_troppo_non_disturbano():
    """«la luce del salotto» e «luce salotto» sono la stessa richiesta."""
    esito = dominio.risolvi("la luce del salotto", TRE_LUCI)

    assert esito.entity_id == "light.salotto"


def test_accenti_e_maiuscole_non_contano():
    dispositivi = [_d("light.veranda", "luce veranda", "Veranda")]

    assert dominio.risolvi("Luce Verandà", dispositivi).entity_id == "light.veranda"


def test_un_riferimento_che_non_corrisponde_a_niente():
    esito = dominio.risolvi("il tostapane", TRE_LUCI)

    assert esito.tipo == dominio.NESSUNO
    assert esito.certo is False


def test_un_riferimento_vuoto_non_corrisponde_a_tutto():
    """Con le parole cercate vuote, un controllo ingenuo direbbe che tutte le
    parole compaiono e prenderebbe il primo dispositivo della casa."""
    assert dominio.risolvi("", TRE_LUCI).tipo == dominio.NESSUNO
    assert dominio.risolvi("   ", TRE_LUCI).tipo == dominio.NESSUNO
    assert dominio.risolvi("la", TRE_LUCI).tipo == dominio.NESSUNO


# =========================================================== l'ambiguita'


def test_un_riferimento_ambiguo_non_sceglie_a_caso():
    """Il test piu' importante di questo file.

    Scegliere a caso fra tre luci e' peggio che chiedere: chi ascolta crede
    di essere stato capito, e la prossima volta ripetera' la stessa frase
    aspettandosi lo stesso risultato.
    """
    esito = dominio.risolvi("luce", TRE_LUCI)

    assert esito.tipo == dominio.AMBIGUO
    assert esito.entity_id == ""
    assert len(esito.alternative) == 3


def test_le_alternative_arrivano_tutte():
    """«Non ho capito quale» non aiuta nessuno: per chiedere «la cucina o il
    salotto?» servono i nomi."""
    esito = dominio.risolvi("luce", TRE_LUCI)

    assert {d.entity_id for d in esito.alternative} == {
        "light.cucina",
        "light.salotto",
        "light.bagno",
    }


def test_le_alternative_sono_in_ordine_stabile():
    """Due chiamate uguali devono dare la stessa frase: un elenco che cambia
    ordine a ogni richiesta fa sembrare rotta una casa che funziona."""
    prima = dominio.risolvi("luce", TRE_LUCI).alternative
    poi = dominio.risolvi("luce", list(reversed(TRE_LUCI))).alternative

    assert [d.entity_id for d in prima] == [d.entity_id for d in poi]


def test_un_alias_esatto_vince_sull_ambiguita():
    """Chi ha chiamato un dispositivo «luce» voleva dire quello, anche se
    esistono «luce cucina» e «luce salotto»."""
    dispositivi = [*TRE_LUCI, _d("light.ingresso", "luce", "Ingresso")]

    esito = dominio.risolvi("luce", dispositivi)

    assert esito.entity_id == "light.ingresso"


# ============================================================== la stanza


def test_la_stanza_di_chi_parla_scioglie_l_ambiguita():
    """Il senso di avere un punto di ascolto per stanza: «accendi la luce»
    detto in cucina vuol dire quella della cucina, e non c'e' bisogno di
    dirlo."""
    esito = dominio.risolvi("luce", TRE_LUCI, stanza="Cucina")

    assert esito.entity_id == "light.cucina"


def test_la_stanza_si_riconosce_senza_badare_a_maiuscole():
    assert dominio.risolvi("luce", TRE_LUCI, stanza="  cucina ").entity_id == "light.cucina"


def test_una_stanza_che_non_c_entra_non_impedisce_il_comando():
    """La stanza restringe, non recinta: un satellite in corridoio che chiede
    la luce del salotto deve poterla accendere."""
    esito = dominio.risolvi("luce salotto", TRE_LUCI, stanza="Corridoio")

    assert esito.entity_id == "light.salotto"


def test_una_stanza_sconosciuta_lascia_l_ambiguita_intatta():
    """Non deve inventare una scelta: se la stanza non ha nessuna di quelle
    luci, si torna alla domanda «quale?»."""
    esito = dominio.risolvi("luce", TRE_LUCI, stanza="Mansarda")

    assert esito.tipo == dominio.AMBIGUO


def test_due_dispositivi_nella_stessa_stanza_restano_ambigui():
    """La stanza non e' una bacchetta magica: due luci in cucina sono due."""
    dispositivi = [
        _d("light.cucina_tavolo", "luce tavolo", "Cucina"),
        _d("light.cucina_piano", "luce piano", "Cucina"),
    ]

    esito = dominio.risolvi("luce", dispositivi, stanza="Cucina")

    assert esito.tipo == dominio.AMBIGUO


def test_senza_stanza_dichiarata_ci_si_comporta_come_prima():
    """Chi non dice da dove parla non deve perdere niente: la dashboard
    aperta sul portatile non ha una stanza, e deve continuare a funzionare."""
    assert dominio.risolvi("luce cucina", TRE_LUCI, stanza="").entity_id == "light.cucina"


# ================================================== come si dice a voce


def test_le_alternative_si_dicono_con_la_stanza_quando_distingue():
    frase = dominio.descrivi_alternative(
        (_d("light.cucina", "luce", "Cucina"), _d("light.salotto", "luce", "Salotto"))
    )

    assert frase == "luce (Cucina) o luce (Salotto)"


def test_la_stanza_non_si_ripete_quando_non_distingue():
    """Ripeterla quando e' la stessa per tutte allunga la frase e non aiuta."""
    frase = dominio.descrivi_alternative(
        (_d("light.tavolo", "luce tavolo", "Cucina"), _d("light.piano", "luce piano", "Cucina"))
    )

    assert frase == "luce tavolo o luce piano"


def test_tre_alternative_si_elencano_con_una_o_sola():
    frase = dominio.descrivi_alternative((_d("a", "prima"), _d("b", "seconda"), _d("c", "terza")))

    assert frase == "prima, seconda o terza"


def test_senza_alias_si_dice_l_identificativo():
    assert dominio.descrivi_alternative((_d("light.x"),)) == "light.x"


# ================================================== dagli alias dell'archivio


def test_gli_alias_dell_archivio_diventano_dispositivi():
    righe = [{"entity_id": "light.x", "alias": "luce", "room": "Cucina", "id": "a1"}]

    dispositivi = dominio.da_alias(righe)

    assert dispositivi == [dominio.Dispositivo("light.x", "luce", "Cucina")]


def test_un_alias_senza_entita_non_e_un_dispositivo():
    """Una riga senza `entity_id` non comanda niente: tenerla vorrebbe dire
    poterla scegliere fra le alternative e poi non fare nulla."""
    assert dominio.da_alias([{"alias": "luce", "room": "Cucina"}]) == []


def test_una_stanza_assente_non_diventa_la_stringa_none():
    dispositivi = dominio.da_alias([{"entity_id": "light.x", "alias": "luce", "room": None}])

    assert dispositivi[0].stanza == ""


@pytest.mark.parametrize("testo,atteso", [("Salottò", "salotto"), ("  CUCINA  ", "cucina"), (None, "")])
def test_la_normalizzazione(testo, atteso):
    assert dominio.normalizza(testo) == atteso
