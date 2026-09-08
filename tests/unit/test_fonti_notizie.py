"""Le fonti che si potevano spegnere e non si spegnevano.

La scheda «Fonti & Notizie» mostrava venti testate con i loro interruttori,
e `news_search.py` leggeva un dizionario scritto nel codice. Si disattivava
ANSA Politica, si chiedevano le notizie, e arrivava politica da ANSA. Nessun
errore: silenzio, che e' peggio, perche' non c'e' niente da leggere e si
finisce col dare la colpa a se stessi.

Stessa storia per `preferred_news_categories`: salvato nell'anagrafica fin
dalla prima versione, scelto nell'interfaccia, mai letto da nessuno. La
rassegna era identica per tutti.

Nessun test qui tocca la rete: `feedparser` e' sostituito, e cio' che si
verifica e' **quali indirizzi andiamo a leggere** — la decisione, non il
trasporto.

Riferimento: issue #26.
"""

from __future__ import annotations

import pytest

from shinra.infra.db import depositi
from shinra.skills import news_search

FONTI = [
    {"id": "a", "name": "ANSA Mondo", "category": "mondo", "url": "http://ansa/mondo", "enabled": True},
    {
        "id": "b",
        "name": "ANSA Politica",
        "category": "politica",
        "url": "http://ansa/politica",
        "enabled": True,
    },
    {"id": "c", "name": "Altro Mondo", "category": "mondo", "url": "http://altro/mondo", "enabled": True},
    {"id": "d", "name": "Spenta", "category": "mondo", "url": "http://spenta", "enabled": False},
]


class FintoFeed:
    def __init__(self, titoli):
        self.entries = [{"title": t, "summary": "", "published": ""} for t in titoli]


@pytest.fixture
def rete(monkeypatch):
    """`feedparser` che annota quali indirizzi legge, senza uscire di casa."""
    letti: list[str] = []
    contenuto: dict[str, list[str]] = {}

    def finto_parse(indirizzo):
        letti.append(indirizzo)
        return FintoFeed(contenuto.get(indirizzo, [f"Notizia da {indirizzo}"]))

    monkeypatch.setattr(news_search.feedparser, "parse", finto_parse)
    return letti, contenuto


@pytest.fixture
def fonti_configurate():
    depositi.fonti.sostituisci_tutto([dict(f) for f in FONTI])


# ----------------------------------------- spegnere una fonte ha effetto


async def test_una_fonte_spenta_non_viene_letta(rete, fonti_configurate):
    letti, _ = rete

    await news_search.get_latest_news("mondo")

    assert "http://spenta" not in letti


async def test_si_leggono_tutte_le_fonti_accese_della_categoria(rete, fonti_configurate):
    letti, _ = rete

    await news_search.get_latest_news("mondo")

    assert sorted(letti) == ["http://altro/mondo", "http://ansa/mondo"]


async def test_le_categorie_non_richieste_restano_fuori(rete, fonti_configurate):
    letti, _ = rete

    await news_search.get_latest_news("mondo")

    assert "http://ansa/politica" not in letti


async def test_spegnere_tutte_le_fonti_si_dice(rete, fonti_configurate):
    """Chi spegne tutto deve sentirselo dire, non ricevere notizie lo stesso
    ne' il silenzio: era proprio la mancanza di effetto il difetto."""
    depositi.fonti.sostituisci_tutto([{**f, "enabled": False} for f in FONTI])
    letti, _ = rete

    esito = await news_search.get_latest_news("mondo")

    assert esito["success"] is False
    assert "Fonti & Notizie" in esito["message"]
    assert letti == []


async def test_una_fonte_senza_il_campo_acceso_vale_accesa(rete):
    """Una fonte aggiunta a mano non deve sparire in silenzio."""
    depositi.fonti.sostituisci_tutto(
        [{"id": "x", "name": "Senza campo", "category": "mondo", "url": "http://x"}]
    )
    letti, _ = rete

    await news_search.get_latest_news("mondo")

    assert letti == ["http://x"]


async def test_senza_nessuna_fonte_configurata_si_ripiega(rete):
    """Installazione nuova o archivio muto: meglio le notizie di ANSA che
    nessuna notizia. E' l'unico caso in cui il dizionario nel codice torna
    utile — non piu' «le fonti», ma una rete di sicurezza."""
    depositi.fonti.sostituisci_tutto([])
    letti, _ = rete

    esito = await news_search.get_latest_news("mondo")

    assert esito["success"] is True
    assert letti == [news_search.FONTI_DI_RIPIEGO["mondo"]]


# ------------------------------------------- le preferenze del profilo


async def test_le_categorie_preferite_scelgono_le_fonti(rete, fonti_configurate):
    letti, _ = rete

    await news_search.get_latest_news(categorie=["politica"])

    assert letti == ["http://ansa/politica"]


async def test_due_profili_con_gusti_diversi_leggono_fonti_diverse(rete, fonti_configurate):
    letti, _ = rete

    await news_search.get_latest_news(categorie=["politica"])
    primo = list(letti)
    letti.clear()
    await news_search.get_latest_news(categorie=["mondo"])

    assert primo == ["http://ansa/politica"]
    assert sorted(letti) == ["http://altro/mondo", "http://ansa/mondo"]


async def test_le_categorie_hanno_la_precedenza_sulla_singola(rete, fonti_configurate):
    letti, _ = rete

    await news_search.get_latest_news(category="mondo", categorie=["politica"])

    assert letti == ["http://ansa/politica"]


# --------------------------------------------- come si mescolano le voci


async def test_una_notizia_per_fonte_a_giro(rete, fonti_configurate):
    """Prendere le prime quattro dalla prima fonte significa che con due
    fonti accese se ne sente una sola, e chi ha acceso la seconda ha ragione
    di aspettarsi il contrario."""
    _, contenuto = rete
    contenuto["http://ansa/mondo"] = ["A1", "A2", "A3", "A4"]
    contenuto["http://altro/mondo"] = ["B1", "B2", "B3", "B4"]

    esito = await news_search.get_latest_news("mondo", max_items=4)

    titoli = [n["titolo"] for n in esito["notizie"]]
    assert set(titoli[:2]) == {"A1", "B1"}
    assert set(titoli[2:]) == {"A2", "B2"}


async def test_una_fonte_muta_non_zittisce_le_altre(rete, fonti_configurate):
    _, contenuto = rete
    contenuto["http://ansa/mondo"] = []
    contenuto["http://altro/mondo"] = ["Unica"]

    esito = await news_search.get_latest_news("mondo")

    assert [n["titolo"] for n in esito["notizie"]] == ["Unica"]


async def test_il_numero_massimo_si_rispetta(rete, fonti_configurate):
    _, contenuto = rete
    contenuto["http://ansa/mondo"] = [f"N{n}" for n in range(20)]
    contenuto["http://altro/mondo"] = [f"M{n}" for n in range(20)]

    esito = await news_search.get_latest_news("mondo", max_items=3)

    assert len(esito["notizie"]) == 3
