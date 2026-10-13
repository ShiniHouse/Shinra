"""Il compito notturno (#259): una volta per giornata, si ferma al tempo massimo, salta senza far rumore, non fa cadere niente."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from shinra.services import compito_notturno as modulo
from shinra.services.compito_notturno import CompitoNotturno

NOTTE = datetime(2026, 10, 14, 3, 0)


async def si() -> bool:
    return True


async def no() -> bool:
    return False


def scarico() -> float:
    return 0.1


def carico_alto() -> float:
    return 3.0


def chiamate():
    visto = {"n": 0}

    async def compito():
        visto["n"] += 1
        return "ok"

    return compito, visto


async def test_un_compito_riuscito_dice_fatto_e_porta_il_risultato():
    compito, visto = chiamate()
    esito = await CompitoNotturno().esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert esito.stato == modulo.FATTO and esito.risultato == "ok" and visto["n"] == 1
    assert esito.giornata == "2026-10-14"


async def test_eseguito_due_volte_nella_stessa_notte_non_fa_niente_la_seconda():
    compito, visto = chiamate()
    c = CompitoNotturno()
    await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    seconda = await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert seconda.stato == modulo.GIA_FATTO
    assert visto["n"] == 1, "il compito e' girato due volte nella stessa giornata"


async def test_la_notte_dopo_gira_di_nuovo():
    compito, visto = chiamate()
    c = CompitoNotturno()
    await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    dopo = await c.esegui(
        "sogno", compito, 5, adesso=datetime(2026, 10, 15, 3, 0), modello_ok=si, carico=scarico
    )
    assert dopo.stato == modulo.FATTO and visto["n"] == 2
    assert c.giornate_fatte("sogno") == ["2026-10-14", "2026-10-15"]


async def test_con_il_modello_spento_salta_subito_e_lo_dice():
    compito, visto = chiamate()
    c = CompitoNotturno()
    esito = await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=no, carico=scarico)
    assert esito.stato == modulo.SALTATO and "modello" in esito.motivo
    assert visto["n"] == 0
    assert esito.durata < 1
    # saltato non vuol dire fatto: la stessa notte, col modello tornato, gira
    ripreso = await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert ripreso.stato == modulo.FATTO


async def test_con_la_macchina_carica_salta():
    compito, visto = chiamate()
    esito = await CompitoNotturno().esegui(
        "sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=carico_alto
    )
    assert esito.stato == modulo.SALTATO and "carica" in esito.motivo and visto["n"] == 0


async def test_dove_il_carico_non_si_conosce_non_salta():
    compito, _ = chiamate()
    esito = await CompitoNotturno().esegui(
        "sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=lambda: None
    )
    assert esito.stato == modulo.FATTO


async def test_al_tempo_massimo_si_interrompe_e_il_compito_riceve_la_cancellazione():
    cancellato = {"si": False}

    async def lento():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancellato["si"] = True
            raise

    c = CompitoNotturno()
    esito = await c.esegui("sogno", lento, 0.05, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert esito.stato == modulo.INTERROTTO and "tempo massimo" in esito.motivo
    assert cancellato["si"], "il compito non ha potuto chiudere in modo pulito"
    assert c.giornate_fatte("sogno") == [], "un compito interrotto non vale come fatto"


async def test_un_errore_nel_compito_non_esce_e_non_vale_come_fatto():
    async def rotto():
        raise RuntimeError("scatola vuota")

    c = CompitoNotturno()
    esito = await c.esegui("sogno", rotto, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert esito.stato == modulo.ERRORE and "scatola vuota" in esito.motivo
    assert c.giornate_fatte("sogno") == []


async def test_un_compito_che_non_usa_il_modello_non_lo_aspetta():
    compito, _ = chiamate()
    esito = await CompitoNotturno().esegui(
        "pulizia", compito, 5, adesso=NOTTE, serve_il_modello=False, modello_ok=no, carico=scarico
    )
    assert esito.stato == modulo.FATTO


async def test_due_compiti_diversi_nella_stessa_notte_non_si_escludono():
    a, visto_a = chiamate()
    b, visto_b = chiamate()
    c = CompitoNotturno()
    await c.esegui("sogno", a, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    await c.esegui("riassunti", b, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert visto_a["n"] == visto_b["n"] == 1


async def test_dimenticare_una_giornata_permette_di_rifarla():
    compito, visto = chiamate()
    c = CompitoNotturno()
    await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    c.dimentica("sogno", date(2026, 10, 14))
    await c.esegui("sogno", compito, 5, adesso=NOTTE, modello_ok=si, carico=scarico)
    assert visto["n"] == 2
