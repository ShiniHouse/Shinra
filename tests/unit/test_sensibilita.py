"""Quali azioni non si fanno sulla parola del modello (issue #192): la tabella, senza rete."""

from __future__ import annotations

import pytest

from shinra.domain import sensibilita as s


@pytest.mark.parametrize(
    ("tool", "argomenti", "attesa"),
    [
        ("get_weather", {"location": "Bologna"}, s.SICURA),
        ("comanda_serratura", {"entity_id": "lock.x", "azione": "sblocca"}, s.SENSIBILE),
        ("comanda_serratura", {"entity_id": "lock.x", "azione": "apri"}, s.SENSIBILE),
        ("comanda_serratura", {"entity_id": "lock.x"}, s.SENSIBILE),  # nel dubbio, si chiede
        ("comanda_serratura", {"entity_id": "lock.x", "azione": "blocca"}, s.SICURA),
        ("comanda_serratura", {"entity_id": "lock.x", "azione": "stato"}, s.SICURA),
        ("comanda_allarme", {"azione": "disarma"}, s.SENSIBILE),
        ("comanda_allarme", {"azione": "arma_fuori"}, s.SICURA),
        ("comanda_allarme", {"azione": "stato"}, s.SICURA),
        ("control_device", {"entity_id": "light.cucina", "action": "turn_on"}, s.SICURA),
        ("control_device", {"entity_id": "lock.x", "action": "turn_off"}, s.SENSIBILE),
        ("control_device", {"entity_id": "alarm_control_panel.casa", "action": "turn_off"}, s.SENSIBILE),
        ("control_device", {"entity_id": "cover.garage", "action": "open"}, s.SENSIBILE),
        ("control_device", {"entity_id": "cover.garage", "action": "close"}, s.SICURA),
        ("control_device", {"entity_id": "cover.porta_ingresso", "action": "open"}, s.SENSIBILE),
        ("control_device", {"entity_id": "cover.salotto", "action": "open"}, s.SICURA),
        ("comanda_tapparella", {"entity_id": "cover.cancello", "azione": "apri"}, s.SENSIBILE),
        ("comanda_tapparella", {"entity_id": "cover.cancello", "azione": "chiudi"}, s.SICURA),
        ("comanda_tapparella", {"entity_id": "cover.camera", "azione": "apri"}, s.SICURA),
        ("activate_scene_or_routine", {"entity_id": "script.qualcosa"}, s.SENSIBILE),
        ("activate_scene_or_routine", {"entity_id": "scene.cinema"}, s.SICURA),
        # Uno strumento che questo modulo non conosce non e' sicuro.
        ("strumento_nuovo", {}, s.SENSIBILE),
        ("cambia_pin", {"pin": "1"}, s.VIETATA),
    ],
)
def test_la_classe_di_un_azione(tool, argomenti, attesa):
    assert s.classifica(tool, argomenti) == attesa


def test_un_nome_naturale_vale_come_il_suo_entity_id():
    """Il modello puo' scrivere «serratura ingresso» invece di `lock.porta`: il controllo vale per tutti e due."""
    alias = {"serratura ingresso": "lock.porta_ingresso", "luce cucina": "light.cucina"}.get
    assert (
        s.classifica("control_device", {"entity_id": "serratura ingresso", "action": "turn_on"}, alias)
        == s.SENSIBILE
    )
    assert (
        s.classifica("control_device", {"entity_id": "luce cucina", "action": "turn_on"}, alias) == s.SICURA
    )
    # Senza alias, il nome stesso tradisce una serratura.
    assert (
        s.classifica("control_device", {"entity_id": "la serratura di casa", "action": "turn_on"})
        == s.SENSIBILE
    )


@pytest.mark.parametrize(
    ("dominio", "servizio", "dati", "attesa"),
    [
        ("lock", "unlock", {"entity_id": "lock.x"}, True),
        ("lock", "open", {"entity_id": "lock.x"}, True),
        ("lock", "lock", {"entity_id": "lock.x"}, False),
        ("alarm_control_panel", "alarm_disarm", {}, True),
        ("alarm_control_panel", "alarm_arm_away", {}, False),
        ("script", "turn_on", {"entity_id": "script.x"}, True),
        ("homeassistant", "turn_on", {"entity_id": ["light.a", "lock.x"]}, True),
        ("homeassistant", "toggle", {"entity_id": "lock.x"}, True),
        ("cover", "open_cover", {"entity_id": "cover.garage"}, True),
        ("cover", "close_cover", {"entity_id": "cover.garage"}, False),
        ("cover", "open_cover", {"entity_id": "cover.salotto"}, False),
        ("light", "turn_on", {"entity_id": "light.cucina"}, False),
    ],
)
def test_i_servizi_di_home_assistant_che_aprono_qualcosa(dominio, servizio, dati, attesa):
    assert s.servizio_sensibile(dominio, servizio, dati) is attesa
