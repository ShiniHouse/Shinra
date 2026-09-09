"""Il promemoria che dice «salvato» deve essere salvato.

Il difetto che questi test esistono per impedire (issue #92): il tool che il
modello chiamava scriveva in una lista Python in memoria, non toccava il
database, non programmava niente nello scheduler, e rispondeva **«Promemoria
salvato»**. Al riavvio spariva. Non suonava mai.

Non aveva nemmeno un errore da leggere — la risposta era che era andato bene
— ed e' il criterio d'uscita della v0.2.0, quello mai verificato in casa:
«un promemoria impostato a voce suona a server riavviato e senza browser
aperto».

I test qui sono di tre tipi:

- **le frasi che cadevano nel vuoto** devono creare un promemoria vero,
  provate una per una dalla tabella della issue;
- **la persistenza**: dopo `add_reminder` deve esserci una riga nel
  database e un job nello scheduler, non un oggetto in memoria;
- **il rifiuto**: quando non si capisce quando, non si dice «salvato».

Riferimento: issue #92.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shinra.domain import quando as tempo
from shinra.infra.db import depositi
from shinra.services.timer_engine import timer_engine
from shinra.skills import reminders

# Mercoledi' 9 settembre 2026, ore 10:00. Un giorno feriale a meta' mattina:
# tutte le attese dei test sono calcolate da qui.
ADESSO = datetime(2026, 9, 9, 10, 0)


@pytest.fixture
def scheduler_finto(monkeypatch):
    """Lo scheduler vero avvia un thread e scrive su SQLite: qui serve solo
    sapere *che* gli e' stato chiesto di suonare."""
    from shinra.infra.scheduler import motore

    programmati: dict[str, tuple] = {}

    class Finto:
        attivo = True

        def programma_promemoria(self, identificativo, testo, quando_iso, utente):
            programmati[identificativo] = (testo, quando_iso, utente)
            return True

        def annulla_promemoria(self, identificativo):
            programmati.pop(identificativo, None)
            return True

        def annulla(self, identificativo):
            return True

    monkeypatch.setattr(motore, "scheduler", Finto())
    return programmati


# ============================================ il difetto, frase per frase


# La tabella della issue #92: otto di queste dieci cadevano al modello, e da
# li' in una lista in memoria.
@pytest.mark.parametrize(
    "frase,quando_atteso",
    [
        ("comprare il pane alle 17:30", datetime(2026, 9, 9, 17, 30)),
        ("prendere le medicine tra 20 minuti", datetime(2026, 9, 9, 10, 20)),
        ("chiamare il dentista domani", datetime(2026, 9, 10, 9, 0)),
        ("prendere le medicine domani mattina", datetime(2026, 9, 10, 9, 0)),
        ("innaffiare le piante sabato", datetime(2026, 9, 12, 9, 0)),
        ("comprare il pane fra due giorni", datetime(2026, 9, 11, 9, 0)),
        ("chiamare mia madre alle 18", datetime(2026, 9, 9, 18, 0)),
        ("pagare il bollo il 15", datetime(2026, 9, 15, 9, 0)),
        ("spegnere il forno stasera", datetime(2026, 9, 9, 20, 0)),
        ("chiamare il commercialista lunedi", datetime(2026, 9, 14, 9, 0)),
    ],
)
def test_le_frasi_che_cadevano_nel_vuoto(frase, quando_atteso):
    """Il dominio le capisce tutte e dieci."""
    assert tempo.quando(frase, ADESSO) == quando_atteso


@pytest.mark.parametrize(
    "frase,testo_atteso",
    [
        ("chiamare il dentista domani mattina", "chiamare il dentista"),
        ("comprare il pane alle 17:30", "comprare il pane"),
        ("innaffiare le piante sabato", "innaffiare le piante"),
        ("spegnere il forno stasera", "spegnere il forno"),
    ],
)
def test_il_quando_viene_tolto_dal_testo(frase, testo_atteso):
    """Un promemoria che suona dicendo «chiamare il dentista domani» e'
    fuorviante: quando suona, quel domani e' diventato oggi."""
    testo, _ = tempo.separa(frase)

    assert testo == testo_atteso


# ============================================ scrive davvero


async def test_il_promemoria_finisce_nel_database(scheduler_finto):
    """Il cuore del difetto. Prima questa asserzione falliva mentre il tool
    rispondeva «Promemoria salvato»."""
    prima = reminders._promemoria_in_attesa()

    esito = await reminders.add_reminder("chiamare il dentista", "domani mattina")

    assert esito["success"] is True
    assert reminders._promemoria_in_attesa() == prima + 1

    righe = depositi.promemoria.attivi()
    assert any("dentista" in str(r.get("text", "")).lower() for r in righe)


async def test_viene_anche_programmata_la_sveglia(scheduler_finto):
    """Scrivere sul database e non programmare il job sarebbe lo stesso
    difetto con un passo in piu': la riga c'e' e non suona."""
    esito = await reminders.add_reminder("chiamare il dentista", "domani mattina")

    identificativo = esito["promemoria"]["id"]

    assert identificativo in scheduler_finto
    testo, quando_iso, _ = scheduler_finto[identificativo]
    assert "dentista" in testo.lower()
    assert quando_iso.startswith(datetime.now().strftime("%Y-%m"))


async def test_sopravvive_a_un_riavvio(scheduler_finto):
    """Il criterio d'uscita della v0.2.0. Il riavvio si simula come lo vive
    il servizio: gli oggetti in memoria si perdono, il database no."""
    await reminders.add_reminder("portare fuori il cane", "domani alle 8")

    # Quel che restava della vecchia implementazione era solo in memoria:
    # dopo un riavvio, un modulo ricaricato non sa piu' niente.
    import importlib

    importlib.reload(reminders)

    esito = await reminders.list_reminders()

    assert esito["totale_attivi"] >= 1
    assert "cane" in esito["message"].lower()


async def test_il_promemoria_e_attribuito_a_chi_lo_ha_chiesto(scheduler_finto):
    from shinra.services import registro

    registro.apri_contesto(attore="giulia", canale="alexa")
    esito = await reminders.add_reminder("prendere le medicine", "alle 18")

    assert esito["promemoria"]["user_id"] == "giulia"


# ============================================ il rifiuto


async def test_senza_un_quando_non_dice_salvato(scheduler_finto):
    """Chi non sa a che ora mettere la sveglia non la mette a caso: chiede."""
    prima = reminders._promemoria_in_attesa()

    esito = await reminders.add_reminder("portare fuori il cane", "")

    assert esito["success"] is False
    assert "salvat" not in esito["message"].lower()
    assert reminders._promemoria_in_attesa() == prima


async def test_il_rifiuto_dice_come_si_fa(scheduler_finto):
    """Un rifiuto che non insegna la formula giusta costringe a indovinare."""
    esito = await reminders.add_reminder("portare fuori il cane", "prima o poi")

    assert esito["serve"] == "quando"
    assert "domani mattina" in esito["message"]


async def test_senza_testo_non_si_crea_niente(scheduler_finto):
    prima = reminders._promemoria_in_attesa()

    esito = await reminders.add_reminder("", "domani")

    assert esito["success"] is False
    assert reminders._promemoria_in_attesa() == prima


async def test_il_quando_dentro_al_testo_viene_capito(scheduler_finto):
    """Il modello scompone la frase come gli pare: chi ha detto «ricordami
    di chiamare il dentista domani» ha detto tutto, anche se il tool riceve
    tutto nel primo parametro."""
    esito = await reminders.add_reminder("chiamare il dentista domani mattina", "")

    assert esito["success"] is True
    assert "dentista" in esito["message"]
    assert "domani" in esito["message"]


# ============================================ leggere quel che c'e'


async def test_list_reminders_legge_il_database(scheduler_finto):
    """Prima leggeva la lista in memoria, e rispondeva «nessun promemoria» a
    chi ne aveva sette."""
    timer_engine.add_reminder(
        "Chiamare il medico", (datetime.now() + timedelta(hours=2)).isoformat(), "alessio"
    )

    esito = await reminders.list_reminders()

    assert esito["totale_attivi"] >= 1
    assert "medico" in esito["message"].lower()


async def test_senza_promemoria_lo_dice(scheduler_finto):
    esito = await reminders.list_reminders()

    assert esito["success"] is True
    assert esito["totale_attivi"] == 0


async def test_cancellare_toglie_anche_la_sveglia(scheduler_finto):
    esito = await reminders.add_reminder("chiamare il dentista", "domani")
    identificativo = esito["promemoria"]["id"]
    assert identificativo in scheduler_finto

    await reminders.delete_reminder(identificativo)

    assert identificativo not in scheduler_finto
    assert reminders._promemoria_in_attesa() == 0


# ============================================ la strada dell'intento


@pytest.mark.parametrize(
    "frase",
    [
        "ricordami di comprare il pane alle 17:30",
        "ricordami di prendere le medicine tra 20 minuti",
        "ricordami di prendere le medicine domani mattina",
        "ricordami di innaffiare le piante sabato",
        "ricordami di comprare il pane fra due giorni",
        "ricordami di spegnere il forno stasera",
        "ricordami di pagare il bollo il 15",
        "segnati che devo chiamare il commercialista lunedi",
    ],
)
def test_l_intento_cattura_quel_che_prima_cadeva(frase):
    """Otto frasi che prima finivano al modello. Adesso l'intento le
    risolve da solo, senza nemmeno chiamarlo."""
    letto = timer_engine.parse_timer_or_reminder(frase)

    assert letto is not None, frase
    assert letto["type"] == "reminder"
    assert letto["text"]


def test_l_intento_non_cattura_cio_che_non_ha_un_quando():
    """Se non c'e' un orario, l'intento deve lasciar perdere: il tool
    chiedera' quando, e chiedere e' meglio che indovinare."""
    assert timer_engine.parse_timer_or_reminder("ricordami di portare fuori il cane") is None


def test_i_timer_continuano_a_funzionare():
    """La modifica tocca il ramo dei promemoria: quello dei timer non deve
    essersi mosso."""
    letto = timer_engine.parse_timer_or_reminder("metti un timer di 10 minuti per la pasta")

    assert letto["type"] == "timer"
    assert letto["duration_seconds"] == 600


# ============================================ che non ritorni


def test_nessuna_lista_in_memoria_nel_modulo():
    """Il difetto in forma di test.

    `_REMINDERS_DB` era una lista Python a livello di modulo: finche' esiste
    un contenitore mutabile li' dentro, esiste un posto dove un promemoria
    puo' sembrare salvato senza esserlo, e sparire al riavvio.

    Si guarda l'albero sintattico e non il testo: la prima versione di questo
    test cercava la stringa `_REMINDERS_DB` nel sorgente e falliva sulla
    docstring del modulo, che cita apposta il vecchio codice per spiegare
    cosa non va rifatto. Il commento che spiega un difetto non e' il difetto.
    """
    import ast
    import inspect

    albero = ast.parse(inspect.getsource(reminders))

    contenitori = [
        bersaglio.id
        for nodo in albero.body
        if isinstance(nodo, (ast.Assign, ast.AnnAssign))
        for bersaglio in (nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target])
        if isinstance(bersaglio, ast.Name)
        and isinstance(getattr(nodo, "value", None), (ast.List, ast.Dict, ast.Set))
        and bersaglio.id != "__all__"
    ]

    assert contenitori == [], (
        "questi contenitori mutabili stanno a livello di modulo e possono "
        f"raccogliere promemoria che non arrivano da nessuna parte: {contenitori}"
    )


# ============================================ i pasti che sono anche ore


@pytest.mark.parametrize(
    "frase,e_un_ora",
    [
        ("cena con Marco", False),
        ("pranzo con i colleghi", False),
        ("dopo cena", True),
        ("a cena", True),
        ("a pranzo", True),
        ("prima di cena", True),
        ("chiamare Marco dopo cena", True),
    ],
)
def test_cena_e_un_pasto_o_un_ora_secondo_la_preposizione(frase, e_un_ora):
    """«Dopo cena» e' un'ora, «cena con Marco» e' il titolo di un impegno.

    Senza questa distinzione «segna cena con Marco» diventava l'impegno «con
    Marco» alle venti: il titolo mangiato dall'orario. L'ha trovato un test
    del calendario, non una rilettura.
    """
    assert (tempo.quando(frase, ADESSO) is not None) is e_un_ora


def test_il_titolo_non_viene_mangiato_dall_orario():
    testo, momento = tempo.separa("cena con Marco")

    assert testo == "cena con marco"
    assert momento is None
