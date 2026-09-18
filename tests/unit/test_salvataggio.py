"""Un salvataggio che porta fuori i segreti non e' un salvataggio: e' una fuga.

La #35 chiedeva di poter mettere al sicuro la configurazione. Il test piu'
importante di questo file non e' quello che verifica il giro completo — e'
`test_nessun_segreto_esce_dall_archivio`, che riempie la casa di credenziali
finte e poi cerca **ogni stringa** nell'archivio intero, serializzato.

E' scritto cosi' apposta. Una guardia che controllasse «la chiave `pin` non
c'e'» resterebbe verde il giorno che qualcuno aggiunge una colonna nuova con
dentro un segreto, o che il PIN finisce dentro `notes`. Cercare il valore
copre anche i casi che non abbiamo previsto.

Riferimento: issue #35.
"""

from __future__ import annotations

import json

import pytest

from shinra.config import secrets as segreti
from shinra.config import settings as impostazioni
from shinra.infra.db import depositi
from shinra.services import salvataggio

# Valori che non devono uscire di casa. Sono riconoscibili apposta: se uno di
# questi compare nell'archivio, si vede a occhio quale.
TOKEN_FINTO = "TOKEN-DI-HOME-ASSISTANT-CHE-NON-DEVE-USCIRE"
PIN_CIFRATO_FINTO = "IMPRONTA-DEL-PIN-CHE-NON-DEVE-USCIRE"
SEGRETO_SESSIONE_FINTO = "SEGRETO-DI-SESSIONE-CHE-NON-DEVE-USCIRE"


@pytest.fixture
def casa_piena():
    """Una casa con dentro qualcosa da salvare, e qualcosa da non far uscire."""
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin", "notes": "il papa'"},
            {"id": "thomas", "name": "Thomas", "role": "teen"},
        ]
    )
    depositi.utenti.imposta_pin("alessio", PIN_CIFRATO_FINTO)
    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "luce del salotto", "entity_id": "light.salotto"}]
    )
    depositi.fatti.sostituisci_tutto(
        [{"id": "f1", "text": "Il cane si chiama Kira", "category": "famiglia", "enabled": True}]
    )
    depositi.modalita.sostituisci_tutto([{"id": "m1", "name": "cinema", "actions": []}])

    prima_token = impostazioni.settings.home_assistant.token
    prima_segreto = impostazioni.settings.security.session_secret
    impostazioni.settings.home_assistant.token = TOKEN_FINTO
    impostazioni.settings.security.session_secret = SEGRETO_SESSIONE_FINTO
    yield
    impostazioni.settings.home_assistant.token = prima_token
    impostazioni.settings.security.session_secret = prima_segreto


# --------------------------------------------------------- i segreti restano


def test_nessun_segreto_esce_dall_archivio(casa_piena):
    """Il criterio di accettazione principale, provato sul testo intero.

    Non si guarda «c'e' la chiave `pin`»: si cerca il **valore**. Cosi' la
    guardia tiene anche se domani un segreto finisce in una colonna nuova, o
    dentro un campo di testo libero, o dentro la configurazione per una
    strada che oggi non esiste.
    """
    testo = json.dumps(salvataggio.esporta(), ensure_ascii=False, default=str)

    for segreto in (TOKEN_FINTO, PIN_CIFRATO_FINTO, SEGRETO_SESSIONE_FINTO):
        assert segreto not in testo, f"«{segreto}» e' finito nell'archivio"


def test_ogni_campo_dichiarato_segreto_nella_configurazione_viene_svuotato(casa_piena):
    """Non basta che i tre valori di prova non compaiano: deve valere per
    tutti i campi che `config/secrets.py` dichiara segreti, anche quelli che
    domani qualcuno aggiungera' li' senza ripassare di qui."""
    configurazione = salvataggio.esporta()["configurazione"]

    for sezione, campo in segreti.CAMPI_SEGRETI:
        valore = (configurazione.get(sezione) or {}).get(campo)
        assert not valore, f"{sezione}.{campo} e' dichiarato segreto e l'archivio lo porta fuori"


def test_l_archivio_porta_le_persone_ma_non_i_loro_pin(casa_piena):
    """Il caso concreto: i profili tornano, i PIN no. Chi ripristina rimette
    i PIN a mano, e questa e' la scelta — non una dimenticanza."""
    tabelle = salvataggio.esporta()["tabelle"]

    nomi = {riga["name"] for riga in tabelle["users"]}
    assert nomi == {"Alessio", "Thomas"}, "l'archivio ha perso per strada le persone di casa"
    for riga in tabelle["users"]:
        assert "pin" not in riga, "la colonna del PIN e' nell'archivio"


def test_anche_l_esportazione_vecchia_ha_smesso_di_scrivere_i_pin(casa_piena, tmp_path):
    """`scripts/esporta_json.py` esiste dalla v0.2.0 e scriveva `users.json`
    con dentro la colonna `pin`. Chiede a questo modulo cos'e' un segreto, e
    questo test verifica che glielo chieda davvero."""
    import importlib.util

    percorso = salvataggio.percorsi.RADICE / "scripts" / "esporta_json.py"
    specifica = importlib.util.spec_from_file_location("esporta_json_in_prova", percorso)
    modulo = importlib.util.module_from_spec(specifica)
    specifica.loader.exec_module(modulo)

    modulo.esporta(tmp_path)
    scritto = (tmp_path / "users.json").read_text(encoding="utf-8")

    assert "Alessio" in scritto, "l'esportazione non scrive piu' niente: il test non guarda nulla"
    assert PIN_CIFRATO_FINTO not in scritto, "l'esportazione vecchia scrive ancora le impronte dei PIN"


# ----------------------------------------------------- il giro completo


def test_un_archivio_ripristinato_riporta_la_casa_com_era(casa_piena, tmp_path):
    """Il primo criterio di accettazione: esporta, cancella tutto, ripristina."""
    percorso = tmp_path / "archivio.json"
    salvataggio.scrivi(percorso)

    depositi.utenti.sostituisci_tutto([])
    depositi.alias.sostituisci_tutto([])
    depositi.fatti.sostituisci_tutto([])
    depositi.modalita.sostituisci_tutto([])
    assert depositi.alias.conta() == 0

    salvataggio.ripristina(salvataggio.leggi(percorso))

    assert {r["name"] for r in depositi.utenti.elenco()} == {"Alessio", "Thomas"}
    assert [r["alias"] for r in depositi.alias.elenco()] == ["luce del salotto"]
    assert [r["text"] for r in depositi.fatti.elenco()] == ["Il cane si chiama Kira"]
    assert [r["name"] for r in depositi.modalita.elenco()] == ["cinema"]


def test_l_anteprima_dice_cosa_si_perde_senza_perderlo(casa_piena, tmp_path):
    """Ripristinare sostituisce. Chi preme il pulsante deve poterlo sapere
    prima, e guardare non deve cambiare niente."""
    percorso = tmp_path / "archivio.json"
    salvataggio.scrivi(percorso)
    depositi.alias.sostituisci_tutto(
        [{"id": f"a{n}", "alias": f"cosa {n}", "entity_id": f"light.l{n}"} for n in range(5)]
    )

    quadro = salvataggio.anteprima(salvataggio.leggi(percorso))

    assert quadro["device_aliases"] == {"adesso": 5, "nell_archivio": 1}
    assert depositi.alias.conta() == 5, "guardare l'anteprima ha cambiato la casa"


def test_una_tabella_che_l_archivio_non_porta_non_viene_svuotata(casa_piena, tmp_path):
    """Un archivio scritto da una versione che non conosceva le modalita' non
    deve cancellare le modalita' di chi lo rilegge. Ripristinare non e'
    «azzera tutto e riscrivi»."""
    percorso = tmp_path / "parziale.json"
    salvataggio.scrivi(percorso)
    archivio = json.loads(percorso.read_text(encoding="utf-8"))
    del archivio["tabelle"]["modes"]
    percorso.write_text(json.dumps(archivio), encoding="utf-8")

    salvataggio.ripristina(salvataggio.leggi(percorso))

    assert [r["name"] for r in depositi.modalita.elenco()] == ["cinema"]


# --------------------------------------------------------- versione e schema


def test_l_archivio_dichiara_di_che_schema_e(casa_piena):
    intestazione = salvataggio.esporta()["shinra"]
    assert intestazione["schema"] == salvataggio.VERSIONE
    assert intestazione["creato_il"], "l'archivio non dice quando e' stato scritto"
    assert intestazione["versione"], "l'archivio non dice da che Shinra viene"


def test_un_archivio_di_domani_viene_rifiutato_invece_che_frainteso(casa_piena, tmp_path):
    """Rileggere uno schema che non si conosce e' peggio che non rileggerlo:
    si ripristina meta' configurazione e si crede di aver finito."""
    percorso = tmp_path / "futuro.json"
    salvataggio.scrivi(percorso)
    archivio = json.loads(percorso.read_text(encoding="utf-8"))
    archivio["shinra"]["schema"] = salvataggio.VERSIONE + 1
    percorso.write_text(json.dumps(archivio), encoding="utf-8")

    with pytest.raises(salvataggio.ArchivioNonValido, match="piu' recente"):
        salvataggio.leggi(percorso)


def test_un_file_che_non_e_un_archivio_lo_dice(tmp_path):
    (tmp_path / "qualunque.json").write_text('{"ciao": 1}', encoding="utf-8")
    with pytest.raises(salvataggio.ArchivioNonValido, match="intestazione"):
        salvataggio.leggi(tmp_path / "qualunque.json")

    (tmp_path / "rotto.json").write_text("{non json", encoding="utf-8")
    with pytest.raises(salvataggio.ArchivioNonValido, match="JSON"):
        salvataggio.leggi(tmp_path / "rotto.json")

    with pytest.raises(salvataggio.ArchivioNonValido, match="non esiste"):
        salvataggio.leggi(tmp_path / "mai-esistito.json")


def test_una_cartella_di_esportazione_vecchia_rientra_migrata(casa_piena, tmp_path):
    """Il terzo criterio di accettazione.

    Lo schema 0 non e' un'invenzione: e' la cartella di file JSON che
    `scripts/esporta_json.py` scrive dalla v0.2.0, e che esiste su disco in
    casa di chi ha seguito quel consiglio. Portava anche i timer, e portava
    la colonna `pin`: entrando, la prima si lascia cadere e la seconda si
    toglie.
    """
    vecchia = tmp_path / "esportazione"
    vecchia.mkdir()
    (vecchia / "users.json").write_text(
        json.dumps([{"id": "alessio", "name": "Alessio", "role": "admin", "pin": PIN_CIFRATO_FINTO}]),
        encoding="utf-8",
    )
    (vecchia / "device_aliases.json").write_text(
        json.dumps([{"id": "a1", "alias": "lampada", "entity_id": "light.l"}]), encoding="utf-8"
    )
    (vecchia / "timers.json").write_text(
        json.dumps([{"id": "t1", "label": "pasta", "completato": False}]), encoding="utf-8"
    )

    archivio = salvataggio.leggi(vecchia)

    assert archivio["shinra"]["schema"] == salvataggio.VERSIONE, "la migrazione non ha alzato lo schema"
    assert "timers" not in archivio["tabelle"], "i timer di allora rientrerebbero in casa"
    assert PIN_CIFRATO_FINTO not in json.dumps(archivio), "un archivio vecchio rimette in giro i PIN"

    salvataggio.ripristina(archivio)
    assert [r["alias"] for r in depositi.alias.elenco()] == ["lampada"]


def test_una_cartella_senza_esportazione_dentro_lo_dice(tmp_path):
    vuota = tmp_path / "vuota"
    vuota.mkdir()
    with pytest.raises(salvataggio.ArchivioNonValido, match="nessun file"):
        salvataggio.leggi(vuota)


# ------------------------------------------------- niente resta non deciso


def test_ogni_tabella_e_stata_decisa():
    """Una tabella nuova non deve poter finire nell'archivio — o restarne
    fuori — senza che qualcuno l'abbia scritto.

    E' la guardia che tiene in piedi tutte le altre: senza, fra sei mesi
    qualcuno aggiunge un deposito con dentro delle credenziali e nessuno se
    ne accorge, perche' nessun test parla di quella tabella.
    """
    decise = set(salvataggio.TABELLE) | set(salvataggio.FUORI)
    non_decise = set(depositi.DEPOSITI) - decise

    assert not non_decise, (
        f"queste tabelle non sono ne' dentro ne' fuori dall'archivio: {sorted(non_decise)}. "
        "Aggiungile a TABELLE o a FUORI in services/salvataggio.py, con scritto perche'."
    )
    assert not (set(salvataggio.TABELLE) & set(salvataggio.FUORI)), "una tabella e' dentro e fuori"


# ------------------------------------------- il salvataggio che si fa da solo


def _archivi_finti(cartella, quanti: int) -> list:
    """`quanti` archivi dai nomi in ordine, come li scriverebbe il servizio."""
    fatti = []
    for n in range(quanti):
        percorso = cartella / f"{salvataggio.PREFISSO}2026010{n}-120000{salvataggio.SUFFISSO}"
        percorso.write_text("{}", encoding="utf-8")
        fatti.append(percorso)
    return fatti


def test_la_rotazione_tiene_i_piu_recenti_e_toglie_i_piu_vecchi(tmp_path):
    archivi = _archivi_finti(tmp_path, 5)

    tolti = salvataggio.ruota(tmp_path, da_conservare=2)

    assert [f.name for f in tolti] == [f.name for f in archivi[:3]]
    assert {f.name for f in tmp_path.iterdir()} == {archivi[3].name, archivi[4].name}


def test_la_rotazione_non_tocca_niente_che_non_abbia_scritto_lei(tmp_path):
    """La cosa piu' pericolosa che questo modulo faccia, e quindi la piu'
    stretta. Nella cartella dei salvataggi puo' finire di tutto: un archivio
    rinominato a mano per metterlo al sicuro, una nota, una copia del
    database. Niente di tutto questo e' roba sua.
    """
    _archivi_finti(tmp_path, 4)
    estranei = {
        "note.txt": "cosa ho cambiato in casa",
        "shinra.db": "non e' un archivio, e' il database",
        "shinra-BUONO-non-cancellare.json.salvato": "rinominato a mano apposta",
        "vecchio-shinra-20250101-120000.json": "non comincia col prefisso",
        "shinra-20250101-120000.json.bak": "non finisce col suffisso",
    }
    for nome, contenuto in estranei.items():
        (tmp_path / nome).write_text(contenuto, encoding="utf-8")
    sottocartella = tmp_path / "vecchi"
    sottocartella.mkdir()
    (sottocartella / f"{salvataggio.PREFISSO}20240101-120000{salvataggio.SUFFISSO}").write_text(
        "{}", encoding="utf-8"
    )

    salvataggio.ruota(tmp_path, da_conservare=1)

    for nome in estranei:
        assert (tmp_path / nome).exists(), f"la rotazione si e' portata via «{nome}»"
    assert list(sottocartella.iterdir()), "la rotazione e' scesa in una sottocartella"


def test_conservarle_tutte_si_dice_e_funziona(tmp_path):
    """Zero non deve voler dire «cancellale tutte», che sarebbe il modo piu'
    rapido di perdere ogni copia con una svista di configurazione."""
    _archivi_finti(tmp_path, 4)

    for valore in (0, -1):
        assert salvataggio.ruota(tmp_path, da_conservare=valore) == []
        assert len(salvataggio.suoi_archivi(tmp_path)) == 4


def test_la_rotazione_ordina_per_nome_non_per_data_di_modifica(tmp_path):
    """Copiare la cartella da qualche parte azzera le date di modifica tutte
    insieme, o le rovescia. Il nome porta il momento in cui l'archivio e'
    stato scritto, e quello resta vero."""
    import os

    archivi = _archivi_finti(tmp_path, 3)
    # Il piu' vecchio per nome, toccato adesso: sembrerebbe il piu' recente.
    os.utime(archivi[0], (10**9 * 2, 10**9 * 2))
    os.utime(archivi[2], (1, 1))

    tolti = salvataggio.ruota(tmp_path, da_conservare=1)

    assert [f.name for f in tolti] == [archivi[0].name, archivi[1].name]
    assert archivi[2].exists(), "e' rimasto l'archivio sbagliato"


def test_una_cartella_che_non_esiste_non_e_un_guasto(tmp_path):
    assert salvataggio.suoi_archivi(tmp_path / "mai-creata") == []
    assert salvataggio.ruota(tmp_path / "mai-creata", da_conservare=3) == []


def test_salvare_viene_prima_di_fare_spazio(casa_piena, tmp_path, monkeypatch):
    """Se la rotazione girasse per prima, un guasto nella scrittura
    lascerebbe una copia in meno e nessuna nuova."""
    monkeypatch.setattr(salvataggio, "cartella_predefinita", lambda: tmp_path)
    _archivi_finti(tmp_path, 3)
    monkeypatch.setattr(impostazioni.settings.salvataggio, "da_conservare", 2)

    percorso = salvataggio.salva_e_ruota()

    rimasti = salvataggio.suoi_archivi(tmp_path)
    assert percorso in rimasti, "l'archivio appena scritto e' stato cancellato dalla rotazione"
    assert len(rimasti) == 2
    assert json.loads(percorso.read_text(encoding="utf-8"))["shinra"]["schema"] == salvataggio.VERSIONE


def test_un_guasto_nel_giro_automatico_non_ferma_la_casa(monkeypatch):
    """Un backup che fa cadere la casa e' peggio di un backup che manca.

    Il logger si sostituisce invece di leggere `caplog`, per la ragione gia'
    scritta in `test_il_testo_detto_non_finisce_nel_log` e in
    `test_il_rifiuto_del_canale_eventi_dice_perche`: l'applicazione installa i
    propri gestori, e un `caplog` che non intercetta niente lascia passare
    qualunque cosa.

    Scritto con `caplog`, questo test passava da solo e falliva nella suite
    intera. E' la terza volta che il progetto ci inciampa, e la terza volta
    che si ripara allo stesso modo.
    """
    scritte: list[str] = []

    class LoggerFinto:
        def exception(self, messaggio, *argomenti):
            scritte.append(messaggio % argomenti if argomenti else messaggio)

        def __getattr__(self, _nome):
            return lambda *a, **k: None

    def esplode():
        raise OSError("disco pieno")

    monkeypatch.setattr(salvataggio, "salva_e_ruota", esplode)
    monkeypatch.setattr(salvataggio, "logger", LoggerFinto())

    salvataggio._gira()  # non deve sollevare

    assert scritte, "il salvataggio automatico e' fallito in silenzio"
    assert any("non e' riuscito" in riga for riga in scritte), scritte


def test_il_servizio_non_parte_se_spento_o_mal_configurato(monkeypatch):
    """Lo scheduler finto dice **sempre di si'**, apposta.

    Scritto la prima volta senza, questo test passava anche togliendo i
    controlli: nella suite lo scheduler non gira, `programma_periodico`
    risponde `False`, e `avvia()` tornava `False` per quel motivo invece che
    per il controllo in prova. Due mutazioni su dodici non mordevano, ed e' il
    modo peggiore di essere verdi — sembra coperto e non lo e'.

    Cosi' invece l'unica cosa che puo' far tornare `False` e' il controllo, e
    si verifica anche che allo scheduler non sia stato chiesto niente.
    """
    from shinra.infra.scheduler import motore

    chiesto = []
    monkeypatch.setattr(
        motore.scheduler,
        "programma_periodico",
        lambda identificativo, funzione, ore: chiesto.append(identificativo) or True,
    )
    servizio = salvataggio.ServizioSalvataggio()

    monkeypatch.setattr(impostazioni.settings.salvataggio, "abilitato", False)
    assert servizio.avvia() is False, "parte anche da spento"
    assert servizio.attivo is False

    monkeypatch.setattr(impostazioni.settings.salvataggio, "abilitato", True)
    for intervallo in (0, -3):
        monkeypatch.setattr(impostazioni.settings.salvataggio, "ogni_ore", intervallo)
        assert servizio.avvia() is False, f"ogni_ore={intervallo} viene accettato come intervallo"
        assert servizio.attivo is False

    assert chiesto == [], f"allo scheduler e' stato chiesto un giro comunque: {chiesto}"


def test_il_servizio_chiede_allo_scheduler_il_giro_giusto(monkeypatch):
    from shinra.infra.scheduler import motore

    chiamate = []
    monkeypatch.setattr(
        motore.scheduler,
        "programma_periodico",
        lambda identificativo, funzione, ore: chiamate.append((identificativo, funzione, ore)) or True,
    )
    monkeypatch.setattr(impostazioni.settings.salvataggio, "abilitato", True)
    monkeypatch.setattr(impostazioni.settings.salvataggio, "ogni_ore", 6.0)

    servizio = salvataggio.ServizioSalvataggio()
    assert servizio.avvia() is True and servizio.attivo is True

    assert len(chiamate) == 1
    identificativo, funzione, ore = chiamate[0]
    assert identificativo == salvataggio.JOB_SALVATAGGIO
    assert funzione is salvataggio._gira, "lo scheduler chiamerebbe qualcos'altro"
    assert ore == 6.0, "l'intervallo della configurazione non arriva allo scheduler"
