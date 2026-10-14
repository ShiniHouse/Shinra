"""Salvare un profilo dalla scheda Utenti non spegne la posizione collegata (#343).

L'interfaccia degli utenti non conosce `entita_posizione` e non la rimanda: senza una difesa, ogni modifica a un nome o a una
lingua riscriveva il campo vuoto, e la persona risultava «non localizzata» senza averlo scelto. E' lo stesso difetto del PIN,
che infatti ha la sua riga nello stesso punto.
"""

from __future__ import annotations

import pytest

from shinra.infra.db import depositi
from shinra.services.user_manager import UserProfile, user_manager


@pytest.fixture(autouse=True)
def utente():
    depositi.utenti.salva(
        {"id": "u_prova", "name": "Prova", "role": "adult", "entita_posizione": "person.prova"}
    )
    yield
    depositi.utenti.cancella("u_prova")


def _letto() -> str:
    return user_manager.get_user_by_id("u_prova").entita_posizione


def test_la_posizione_collegata_si_legge_dal_profilo():
    assert _letto() == "person.prova"


def test_salvare_il_profilo_senza_quel_campo_non_la_spegne():
    """Il corpo che manda la scheda Utenti: nome e ruolo, niente posizione."""
    user_manager.upsert_user(
        UserProfile.model_validate({"id": "u_prova", "name": "Prova Rinominata", "role": "adult"})
    )
    assert (
        _letto() == "person.prova"
    ), "la posizione e' stata cancellata da un salvataggio che non la nominava"
    assert user_manager.get_user_by_id("u_prova").name == "Prova Rinominata"


def test_dirlo_esplicitamente_la_spegne_o_la_cambia():
    user_manager.upsert_user(
        UserProfile.model_validate(
            {"id": "u_prova", "name": "Prova", "role": "adult", "entita_posizione": ""}
        )
    )
    assert _letto() == ""

    user_manager.upsert_user(
        UserProfile.model_validate(
            {"id": "u_prova", "name": "Prova", "role": "adult", "entita_posizione": "device_tracker.altro"}
        )
    )
    assert _letto() == "device_tracker.altro"


def test_un_profilo_nuovo_nasce_senza_posizione():
    try:
        user_manager.upsert_user(
            UserProfile.model_validate({"id": "u_nuovo", "name": "Nuovo", "role": "guest"})
        )
        assert user_manager.get_user_by_id("u_nuovo").entita_posizione == ""
    finally:
        depositi.utenti.cancella("u_nuovo")
