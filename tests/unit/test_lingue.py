"""Aggiungere una lingua non deve richiedere di toccare il codice.

E' il primo criterio di accettazione della #36, e la scheda dice perche' non
era vero: «non e' un problema di traduzione delle etichette: e' la logica di
comprensione a essere monolingue». Gli schemi con cui Shinra capisce una frase
— i verbi che accendono, le parole del meteo, le frasi che aprono l'intervista
— erano costanti dentro `casa.py`, `informazioni.py` e `promemoria.py`.

Il test che conta e' `test_una_lingua_nuova_non_richiede_di_toccare_il_codice`:
scrive una lingua inventata in una cartella temporanea e chiede agli intenti
veri di capirla. Se passa, il criterio e' soddisfatto per costruzione; tutti
gli altri test di questo file sono contorno.

Riferimento: issue #36.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest
import yaml

from shinra.services.intenti import lingue

RADICE = Path(__file__).resolve().parent.parent.parent
INTENTI = RADICE / "src" / "shinra" / "services" / "intenti"


@pytest.fixture(autouse=True)
def _senza_memoria():
    """Gli schemi sono in cache: fra un test e l'altro si azzera, o il primo
    decide per tutti."""
    lingue._compila.cache_clear()
    yield
    lingue._compila.cache_clear()


# ------------------------------------------------- il criterio della #36


@pytest.fixture()
def lingua_inventata(tmp_path, monkeypatch) -> str:
    """Una lingua che non esiste, scritta adesso, senza toccare una riga di
    codice. Le parole sono inventate apposta: se un intento continuasse a
    capire l'italiano vorrebbe dire che ha ancora i suoi schemi dentro."""
    dati = {
        "lingua": "zz",
        "nome": "inventata",
        "casa": {
            "segnali_interni": ["nel bloop"],
            "controllo_dispositivo": r"^(zap|unzap)\s+(.+)$",
            "verbi_che_accendono": ["zap"],
        },
        "meteo": {"parole": ["blorp"], "citta": r"\bverso\s+([A-Z]\w*)", "domani": "dopo"},
        "enciclopedia": {"inneschi": ["spiegoni su"], "pulizia": r"^(spiegoni su)\s+"},
        "apprendimento": {"avvii": ["impara tutto"], "interruzioni": ["basta cosi"]},
    }
    (tmp_path / "zz.yaml").write_text(yaml.safe_dump(dati, allow_unicode=True), encoding="utf-8")
    # L'italiano resta accanto: e' la lingua di ripiego, e toglierlo
    # proverebbe un'altra cosa.
    (tmp_path / "it.yaml").write_text(
        (lingue.CARTELLA / "it.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(lingue, "CARTELLA", tmp_path)
    # E la lingua si sceglie **dalla configurazione**, non passandola a mano:
    # e' cosi' che la sceglierebbe chi installa Shinra.
    from shinra.config import settings as impostazioni

    monkeypatch.setattr(impostazioni.settings.assistant, "language", "zz")
    return "zz"


def test_una_lingua_nuova_non_richiede_di_toccare_il_codice(lingua_inventata):
    """Il criterio, provato invece che dichiarato.

    Gli intenti sono quelli veri, importati da dove stanno. L'unica cosa
    cambiata e' un file YAML in una cartella temporanea.
    """
    from shinra.services.intenti.casa import ControlloDispositivo
    from shinra.services.intenti.informazioni import Enciclopedia, Meteo

    schemi = lingue.schemi(lingua_inventata)
    assert schemi.lingua == "zz"

    class FintaRichiesta:
        def __init__(self, testo):
            self.testo = testo
            self.minuscolo = testo.lower()

    # Il controllo dei dispositivi capisce il verbo inventato...
    trovato = schemi.controllo_dispositivo.match("zap la cosa")
    assert trovato, "il controllo dispositivi non parla la lingua nuova"
    assert trovato.group(1) in schemi.verbi_che_accendono

    # ...e non capisce piu' l'italiano, che e' la meta' che conta: se lo
    # capisse ancora, vorrebbe dire che gli schemi sono rimasti nel codice.
    assert not schemi.controllo_dispositivo.match("accendi la luce")

    assert Meteo().applicabile(FintaRichiesta("che blorp fa domani"))
    assert not Meteo().applicabile(FintaRichiesta("che meteo fa domani"))

    assert Enciclopedia().applicabile(FintaRichiesta("spiegoni su Roma"))
    assert not Enciclopedia().applicabile(FintaRichiesta("cosa significa deriva"))

    # `applicabile` dell'apprendimento chiede anche al motore se c'e' una
    # sessione aperta: qui interessa solo che la frase venga riconosciuta.
    assert any(t in "impara tutto adesso" for t in schemi.avvii_apprendimento)
    assert not any(t in "kyra istruisci" for t in schemi.avvii_apprendimento)
    assert ControlloDispositivo().nome == "controllo-dispositivo"

    # E non solo `applicabile`: anche cio' che gli intenti leggono **dentro**
    # una frase. Il meteo guarda se e' stato chiesto il giorno dopo, e quella
    # parola e' uno schema come gli altri.
    previsioni = {
        "localita": "Zzville",
        "previsioni": [{"temp_max": 20}, {"condizione": "Sereno", "temp_max": 22, "temp_min": 11}],
        "adesso": {"temperatura": "18", "condizione": "Nuvoloso"},
    }
    assert "22" in Meteo._frase(
        previsioni, "che blorp fa dopo"
    ), "il meteo non legge il «domani» della lingua nuova"
    assert "22" not in Meteo._frase(
        previsioni, "che blorp fa domani"
    ), "il meteo capisce ancora «domani» in italiano: quella parola e' rimasta nel codice"


def test_cambiare_lingua_non_richiede_un_riavvio(lingua_inventata, monkeypatch):
    """Gli intenti nascono quando il modulo si carica: se leggessero gli
    schemi li', cambiare lingua dalle impostazioni non farebbe niente fino al
    riavvio del servizio — e nessuna schermata lo direbbe.

    Qui la lingua si cambia a programma acceso, e il comportamento deve
    cambiare con lei.
    """
    from shinra.config import settings as impostazioni
    from shinra.services.intenti.informazioni import Meteo

    class FintaRichiesta:
        def __init__(self, testo):
            self.testo = testo
            self.minuscolo = testo.lower()

    assert Meteo().applicabile(FintaRichiesta("che blorp fa"))
    assert not Meteo().applicabile(FintaRichiesta("che meteo fa"))

    monkeypatch.setattr(impostazioni.settings.assistant, "language", "it")

    assert Meteo().applicabile(FintaRichiesta("che meteo fa")), (
        "la lingua e' cambiata e l'intento parla ancora quella di prima: "
        "gli schemi vengono letti una volta sola, al caricamento"
    )
    assert not Meteo().applicabile(FintaRichiesta("che blorp fa"))


# ------------------------------------------------- il caricatore


def test_una_chiave_mancante_si_dice_per_nome(tmp_path, monkeypatch):
    """Il guasto peggiore sarebbe silenzioso: un intento che smette di
    capire una frase ha lo stesso sintomo di un modello che non ha capito, e
    si passa un pomeriggio a guardare dalla parte sbagliata."""
    incompleta = {"lingua": "xx", "casa": {"segnali_interni": ["qui"]}}
    (tmp_path / "xx.yaml").write_text(yaml.safe_dump(incompleta), encoding="utf-8")
    monkeypatch.setattr(lingue, "CARTELLA", tmp_path)

    with pytest.raises(lingue.LinguaIncompleta) as errore:
        lingue._compila("xx")

    detto = str(errore.value)
    assert "xx.yaml" in detto, f"non dice di quale file parla: {detto}"
    assert "casa.controllo_dispositivo" in detto, f"non dice quale chiave manca: {detto}"
    assert "meteo.parole" in detto, "dice solo la prima chiave mancante e non le altre"


def test_una_lingua_che_non_esiste_non_spegne_la_casa(monkeypatch, caplog):
    """Un refuso in `config.yaml` e' una cosa che succede. Se rendesse Shinra
    muta sarebbe un guasto sproporzionato alla causa: si ripiega
    sull'italiano."""
    schemi = lingue.schemi("klingon")
    assert schemi.lingua == "it"
    assert "accendi" in schemi.verbi_che_accendono


def test_l_italiano_che_manca_invece_si_deve_sentire(tmp_path, monkeypatch):
    """La ricaduta ha un fondo: se manca anche la lingua di ripiego, tacere
    vorrebbe dire una casa che non capisce piu' niente senza dirlo."""
    monkeypatch.setattr(lingue, "CARTELLA", tmp_path)
    with pytest.raises(FileNotFoundError):
        lingue.schemi("it")


def test_le_lingue_disponibili_si_leggono_dalla_cartella():
    """Una lingua nuova entra nell'elenco il giorno che il suo file nasce, non
    il giorno che qualcuno si ricorda di aggiungerla a una tupla."""
    assert "it" in lingue.lingue_disponibili()


def test_l_italiano_e_completo():
    """La lingua di riferimento deve avere tutto cio' che il codice legge."""
    schemi = lingue.schemi("it")
    assert schemi.nome == "italiano"
    assert len(schemi.segnali_interni) > 10
    assert "accendi" in schemi.verbi_che_accendono
    assert "meteo" in schemi.parole_meteo
    assert schemi.controllo_dispositivo.match("accendi la luce della cucina")
    assert schemi.citta.search("che tempo fa a Reggio Emilia")
    assert schemi.pulizia_enciclopedia.sub("", "cosa significa deriva") == "deriva"


# ------------------------------------------- niente italiano nella logica


# Parole italiane che, trovate in una **stringa** dentro un intento,
# vorrebbero dire che uno schema e' tornato nel codice. Sono i verbi e le
# frasi che decidono, non le parole delle risposte — quelle sono il prossimo
# pezzo della #36.
#
# Si guardano solo le stringhe e non tutto il testo: `previsioni` e' il nome
# di una variabile e una chiave della risposta del servizio meteo, e cercarla
# ovunque accusava una riga giusta. Una guardia che grida al lupo su un
# innocente viene disattivata alla seconda volta.
SPIE = ("accendi", "spegni", "disattiva", "cosa significa", "istruisci", "in salotto")

# `domani` non e' fra le spie, e vale la pena dire perche': e' uno schema —
# sta nella lingua, `meteo.domani` — ma compare anche in una **risposta**,
# «Domani a Roma sereno». Una guardia che lo cercasse accuserebbe quella
# frase, che e' giusta dov'e'. Le sei qui sopra non compaiono in nessuna
# risposta, ed e' per questo che sono loro.


def _stringhe(codice: str) -> str:
    """Tutte le stringhe del file, docstring escluse, chieste al tokenizzatore.

    La prima versione le cercava con un'espressione regolare, e sbagliava:
    un apostrofo dentro una stringa a virgolette doppie — `{sola[\'nome\']}` —
    sfasa l\'accoppiamento delle virgolette da li\' in avanti, e mezzo file
    smette di essere guardato. La guardia passava e non guardava niente; l\'ha
    detto una mutazione, non una rilettura.

    Le docstring si riconoscono dalle virgolette triple e si saltano: spiegano
    con esempi — «Accendi la luce della cucina» — e un esempio non e\' uno
    schema.
    """
    pezzi = []
    for pezzo in tokenize.generate_tokens(io.StringIO(codice).readline):
        if pezzo.type != tokenize.STRING:
            continue
        if pezzo.string.lstrip("rbfuRBFU").startswith(('"""', "'''")):
            continue
        pezzi.append(pezzo.string.lower())
    return " ".join(pezzi)


def test_gli_intenti_non_contengono_piu_gli_schemi_in_italiano():
    """La meta' che il test del criterio non copre.

    Quello prova che una lingua nuova **funziona**; questo che la vecchia non
    e' rimasta anche dentro il codice — che sarebbe il modo di far passare il
    criterio e continuare a modificare la logica a ogni lingua.

    Le stringhe rivolte all'utente restano dove sono, ed e' voluto: sono il
    prossimo pezzo della #36, e mescolare i due lavori renderebbe illeggibile
    il momento in cui uno dei due ha rotto qualcosa.
    """
    colpevoli = []
    guardati = 0
    for percorso in sorted(INTENTI.glob("*.py")):
        stringhe = _stringhe(percorso.read_text(encoding="utf-8"))
        guardati += len(stringhe)
        for spia in SPIE:
            if spia in stringhe:
                colpevoli.append(f"{percorso.name}: «{spia}»")

    assert guardati > 2000, f"le stringhe guardate sono {guardati}: la guardia non guarda piu' niente"

    assert colpevoli == [], (
        "questi schemi sono tornati dentro la logica invece di stare nel file " f"della lingua: {colpevoli}"
    )


def test_ogni_schema_che_il_codice_legge_e_dichiarato_nel_caricatore():
    """`RICHIESTE` e' l'elenco che permette di dire «manca questa chiave».

    Se un campo di `Schemi` non ci fosse, una lingua incompleta passerebbe la
    verifica e scoppierebbe dopo, dentro un intento — che e' proprio il guasto
    che l'elenco esiste per evitare.
    """
    dichiarate = {".".join(p) for p in lingue.RICHIESTE}
    assert len(dichiarate) == len(lingue.RICHIESTE), "una richiesta e' ripetuta"

    # Ogni campo di `Schemi`, tranne i due che descrivono la lingua stessa,
    # deve nascere da una chiave verificata.
    campi = set(lingue.Schemi.__dataclass_fields__) - {"lingua", "nome"}
    assert len(campi) == len(lingue.RICHIESTE), (
        f"`Schemi` ha {len(campi)} campi e il caricatore ne verifica "
        f"{len(lingue.RICHIESTE)}: uno dei due elenchi e' rimasto indietro"
    )
