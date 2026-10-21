"""Quanto lavora il server di casa: processore, memoria, disco, calore (la colonna «server» della dashboard).

Senza dipendenze nuove: sul server (Linux) si legge `/proc`. Dove `/proc` non c'e' (un PC di sviluppo) si risponde
`disponibile: false` e la dashboard nasconde il pannello, invece di inventare numeri.

Niente di cio' che si dice in casa passa di qui: solo percentuali e megabyte. Non si espongono nomi di macchina, indirizzi
o processi.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Any, Optional

PROC = Path("/proc")
TERMICA = Path("/sys/class/thermal/thermal_zone0/temp")
CAMPIONE_MINIMO_S = (
    0.25  # fra due letture della CPU serve un po' di tempo, altrimenti la differenza e' rumore
)

_ultimo: Optional[tuple[float, int, int]] = None  # (istante, ozioso, totale)


def cpu_da_stat(testo: str) -> Optional[tuple[int, int]]:
    """`(ozioso, totale)` dai tick della prima riga di `/proc/stat` (`cpu  user nice system idle iowait ...`)."""
    for riga in testo.splitlines():
        parti = riga.split()
        if parti and parti[0] == "cpu" and len(parti) >= 5:
            try:
                valori = [int(x) for x in parti[1:]]
            except ValueError:
                return None
            ozioso = valori[3] + (valori[4] if len(valori) > 4 else 0)  # idle + iowait
            return ozioso, sum(valori[:8])
    return None


def memoria_da_meminfo(testo: str) -> Optional[dict[str, Any]]:
    """Memoria usata, come la intende chi guarda: totale meno cio' che si puo' ancora dare (`MemAvailable`)."""
    kb: dict[str, int] = {}
    for riga in testo.splitlines():
        nome, _, resto = riga.partition(":")
        pezzo = resto.split()
        if pezzo and pezzo[0].isdigit():
            kb[nome] = int(pezzo[0])
    if "MemTotal" not in kb or "MemAvailable" not in kb or kb["MemTotal"] <= 0:
        return None
    usata = kb["MemTotal"] - kb["MemAvailable"]
    return {
        "percentuale": round(100 * usata / kb["MemTotal"]),
        "usata_mb": usata // 1024,
        "totale_mb": kb["MemTotal"] // 1024,
    }


def percentuale_cpu(prima: tuple[int, int], dopo: tuple[int, int]) -> Optional[int]:
    totale = dopo[1] - prima[1]
    if totale <= 0:
        return None
    ozioso = dopo[0] - prima[0]
    return max(0, min(100, round(100 * (totale - ozioso) / totale)))


def _leggi(percorso: Path) -> Optional[str]:
    try:
        return percorso.read_text(encoding="utf-8")
    except OSError:
        return None


async def _cpu() -> Optional[int]:
    """La CPU dall'ultima lettura; alla prima ne fa due a breve distanza."""
    global _ultimo
    adesso = _leggi(PROC / "stat")
    lettura = cpu_da_stat(adesso) if adesso else None
    if lettura is None:
        return None
    ora = time.monotonic()
    if _ultimo is None or ora - _ultimo[0] < CAMPIONE_MINIMO_S:
        precedente = lettura
        await asyncio.sleep(CAMPIONE_MINIMO_S)
        di_nuovo = _leggi(PROC / "stat")
        lettura = cpu_da_stat(di_nuovo) if di_nuovo else None
        if lettura is None:
            return None
        ora = time.monotonic()
    else:
        precedente = (_ultimo[1], _ultimo[2])
    _ultimo = (ora, lettura[0], lettura[1])
    return percentuale_cpu(precedente, lettura)


def _temperatura() -> Optional[float]:
    testo = _leggi(TERMICA)
    try:
        return round(int(testo) / 1000, 1) if testo else None
    except ValueError:
        return None


async def campiona() -> dict[str, Any]:
    """Lo stato del server adesso. `disponibile` e' falso se non si puo' leggere `/proc`."""
    meminfo = _leggi(PROC / "meminfo")
    memoria = memoria_da_meminfo(meminfo) if meminfo else None
    if memoria is None:
        return {"disponibile": False}
    cpu = await _cpu()
    try:
        disco = shutil.disk_usage("/")
        uso_disco: Optional[dict[str, Any]] = {
            "percentuale": round(100 * disco.used / disco.total),
            "libero_gb": round(disco.free / 1024**3, 1),
        }
    except OSError:
        uso_disco = None
    caricamento = _leggi(PROC / "loadavg")
    return {
        "disponibile": True,
        "cpu": cpu,
        "memoria": memoria,
        "disco": uso_disco,
        "carico": float(caricamento.split()[0]) if caricamento else None,
        "temperatura_c": _temperatura(),
    }
