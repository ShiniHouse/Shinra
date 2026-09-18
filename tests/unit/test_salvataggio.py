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
