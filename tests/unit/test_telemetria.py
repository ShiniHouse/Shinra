"""La telemetria del server: legge `/proc` senza inventare niente, e dove non c'e' lo dice."""

from __future__ import annotations

import pytest

from shinra.services import telemetria

STAT = "cpu  4705 150 1120 16250 520 0 30 0 0 0\ncpu0 1 2 3 4 5\n"
MEMINFO = (
    "MemTotal:        8000000 kB\nMemFree:          500000 kB\nMemAvailable:    2000000 kB\nBuffers: 10 kB\n"
)


def test_i_tick_della_cpu_diventano_ozioso_e_totale():
    # ozioso = idle + iowait = 16250 + 520; totale = somma dei primi otto campi
    assert telemetria.cpu_da_stat(STAT) == (16770, 4705 + 150 + 1120 + 16250 + 520 + 0 + 30 + 0)


@pytest.mark.parametrize("testo", ["", "intr 1 2 3", "cpu  1 2", "cpu  a b c d e"])
def test_uno_stat_illeggibile_non_da_numeri(testo):
    assert telemetria.cpu_da_stat(testo) is None


def test_la_percentuale_e_il_lavoro_fra_due_letture():
    assert telemetria.percentuale_cpu((100, 1000), (150, 1200)) == 75  # 200 tick, 50 oziosi
    assert telemetria.percentuale_cpu((100, 1000), (100, 1000)) is None  # nessun tempo passato
    assert telemetria.percentuale_cpu((0, 0), (500, 100)) == 0  # mai negativa


def test_la_memoria_usata_e_totale_meno_disponibile():
    m = telemetria.memoria_da_meminfo(MEMINFO)
    assert m == {"percentuale": 75, "usata_mb": 5859, "totale_mb": 7812}


@pytest.mark.parametrize("testo", ["", "MemTotal: 0 kB\nMemAvailable: 0 kB", "MemFree: 1 kB"])
def test_un_meminfo_incompleto_non_da_numeri(testo):
    assert telemetria.memoria_da_meminfo(testo) is None


async def test_senza_proc_si_dice_che_non_c_e(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetria, "PROC", tmp_path)
    assert await telemetria.campiona() == {"disponibile": False}


async def test_con_un_proc_finto_si_campiona_tutto(tmp_path, monkeypatch):
    (tmp_path / "stat").write_text(STAT)
    (tmp_path / "meminfo").write_text(MEMINFO)
    (tmp_path / "loadavg").write_text("0.52 0.40 0.30 1/200 999\n")
    monkeypatch.setattr(telemetria, "PROC", tmp_path)
    monkeypatch.setattr(telemetria, "TERMICA", tmp_path / "non-c-e")
    monkeypatch.setattr(telemetria, "_ultimo", None)
    monkeypatch.setattr(telemetria, "CAMPIONE_MINIMO_S", 0.0)
    r = await telemetria.campiona()
    assert r["disponibile"] is True and r["memoria"]["percentuale"] == 75
    assert r["carico"] == 0.52 and r["temperatura_c"] is None
    assert r["cpu"] is None or 0 <= r["cpu"] <= 100  # stesse due letture: nessun tempo passato


def test_la_temperatura_si_legge_in_gradi(tmp_path, monkeypatch):
    f = tmp_path / "temp"
    f.write_text("47500\n")
    monkeypatch.setattr(telemetria, "TERMICA", f)
    assert telemetria._temperatura() == 47.5
    f.write_text("caldo")
    assert telemetria._temperatura() is None
