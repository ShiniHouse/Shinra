"""Verifica che ogni impostazione esposta all'utente abbia un consumatore.

La revisione tecnica ha individuato nove elementi che l'interfaccia o il file di
configurazione presentano come funzionanti e che nessuna riga di codice legge —
la «configurazione fantasma». Non producono errori: producono silenzio, il che
li rende piu' insidiosi di un difetto visibile.

Questi test sono il presidio che impedisce al fenomeno di ripetersi.
Riferimento: issue v0.3.0 #26.
"""

from __future__ import annotations

from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
SORGENTI = [RADICE / "src" / "shinra"]


def occorrenze(simbolo: str, escludi: tuple[str, ...] = ()) -> list[str]:
    """File Python che nominano il simbolo, esclusi quelli indicati.

    `config/secrets.py` va quasi sempre escluso: rendere un campo
    impostabile dall'ambiente non significa che qualcuno lo usi per cio'
    a cui serve. Un test che si dichiara soddisfatto a vuoto e' peggio di
    nessun test.
    """
    trovati = []
    for radice in SORGENTI:
        if not radice.is_dir():
            continue
        for percorso in radice.rglob("*.py"):
            if percorso.name in escludi or "__pycache__" in percorso.parts:
                continue
            if simbolo in percorso.read_text(encoding="utf-8"):
                trovati.append(str(percorso.relative_to(RADICE)))
    return trovati


def test_le_fonti_rss_configurate_sono_usate() -> None:
    """Era `xfail(strict=True)` dalla v0.1.0. Il marcatore e' caduto con la
    issue #26, che e' il modo in cui questo progetto dichiara risolto un
    difetto: quando la correzione arriva, il test diventa rosso finche' non
    si toglie la dichiarazione di resa."""
    assert occorrenze("get_sources", escludi=("data_store.py", "routes_admin.py")), (
        "data/sources.json e il gestore fonti dell'interfaccia non hanno alcun effetto: "
        "src/shinra/skills/news_search.py usa un dizionario RSS_FEEDS scritto nel codice"
    )


def test_le_categorie_di_notizie_preferite_sono_usate() -> None:
    # Escludiamo i moduli che il campo lo conservano soltanto: l'anagrafica e
    # lo strato di persistenza. Conservare non e' usare, e un test che si
    # dichiara soddisfatto perche' qualcuno ha nominato il campo in una
    # tabella non presidia piu' niente.
    assert occorrenze(
        "preferred_news_categories",
        escludi=("user_manager.py", "modelli.py", "depositi.py"),
    ), (
        "Il campo e' salvato in users.json ma nessun codice lo consuma: "
        "il briefing notizie e' identico per tutti gli utenti"
    )


def test_gli_argomenti_vietati_sono_applicati() -> None:
    """Risolto dalla issue #8: il filtro esiste ed e' applicato nell'agente."""
    assert occorrenze("restricted_topics", escludi=("user_manager.py",)), (
        "Nessun filtro sui contenuti per i minori: il profilo 'child' cambia "
        "solo il tono del prompt, non cio' a cui puo' accedere"
    )


def test_l_application_id_di_alexa_e_verificato() -> None:
    """Risolto dalla issue #4: /api/alexa confronta l'applicationId.

    Il marcatore xfail e' stato rimosso quando la verifica e' entrata in
    funzione — e' il segnale che il difetto e' chiuso, non solo dichiarato tale.
    """
    assert occorrenze("skill_id", escludi=("settings.py", "secrets.py")), (
        "settings.alexa.skill_id non e' letto da nessuna riga: /api/alexa non "
        "verifica da quale skill provenga la richiesta"
    )


def test_l_annuncio_su_echo_e_utilizzato() -> None:
    """Risolto dalla issue #11: il canale di consegna la usa per annunciare
    timer e promemoria scaduti su un dispositivo Echo."""
    assert occorrenze("speak_on_alexa", escludi=("ha_client.py",)), (
        "src/shinra/infra/homeassistant/client.py definisce speak_on_alexa() ma nessuno la chiama: "
        "l'assistente non puo' parlare spontaneamente su un dispositivo Echo"
    )


def test_il_segreto_di_sessione_e_utilizzato() -> None:
    """Risolto dalla issue #6: i token di sessione sono firmati con esso."""
    assert occorrenze(
        "session_secret", escludi=("settings.py", "secrets.py")
    ), "I token di sessione sono generati con secrets.token_hex e non firmati"


def test_nessuna_dipendenza_dichiarata_e_inutilizzata() -> None:
    """duckduckgo-search e' in requirements.txt e non e' importata da nessuna parte.

    Questo test resta verde perche' verifica la coerenza di pyproject.toml, che
    e' il file di riferimento dalla v0.1.0. requirements.txt viene ripulito
    nella issue v0.1.0 #10.
    """
    pyproject = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    assert "duckduckgo" not in pyproject, (
        "duckduckgo-search non e' importata da nessun modulo: non deve comparire " "fra le dipendenze"
    )


# ------------------------------------------------- la configurazione ricaricata


MODULI_CHE_IMPORTANO_SETTINGS = (
    "shinra.api.sicurezza",
    "shinra.api.routes_admin",
    "shinra.services.agent",
    "shinra.services.consegna",
    "shinra.config.prompt_templates",
    "shinra.channels.alexa.skill_handler",
)


def test_c_e_una_sola_configurazione_per_tutti() -> None:
    """Ogni `from config.settings import settings` deve guardare lo stesso oggetto.

    Se `reload_settings()` ne creasse uno nuovo, questi moduli resterebbero
    legati al vecchio: dopo un salvataggio dal pannello impostazioni
    leggerebbero i valori di prima fino al riavvio del servizio. E'
    esattamente il difetto REL-04 (issue #9) in un altro punto del codice.
    """
    import importlib

    from shinra.config import settings as modulo

    for nome in MODULI_CHE_IMPORTANO_SETTINGS:
        m = importlib.import_module(nome)
        assert (
            m.settings is modulo.settings
        ), f"{nome} ha una copia della configurazione invece di quella condivisa"


def test_dopo_un_ricarico_i_moduli_vedono_i_valori_nuovi(monkeypatch) -> None:
    """La prova che conta: cambiare la configurazione arriva a chi la usa."""
    from shinra.api import sicurezza
    from shinra.config import settings as modulo

    nome_originale = modulo.settings.assistant.name

    ricaricato = modulo.load_config()
    ricaricato.assistant.name = "NomeDiProva"
    ricaricato.security.auth_enabled = not modulo.settings.security.auth_enabled
    monkeypatch.setattr(modulo, "load_config", lambda: ricaricato)

    try:
        modulo.reload_settings()
        assert sicurezza.settings is modulo.settings
        assert sicurezza.settings.assistant.name == "NomeDiProva"
        assert sicurezza.settings.security.auth_enabled == ricaricato.security.auth_enabled
    finally:
        monkeypatch.undo()
        modulo.reload_settings()

    assert modulo.settings.assistant.name == nome_originale


def test_le_dipendenze_sono_dichiarate_in_un_posto_solo() -> None:
    """requirements.txt non deve elencare pacchetti: deve rimandare a pyproject.

    Quando i due elenchi erano separati, il secondo e' rimasto indietro:
    mancavano cryptography, apscheduler, sqlalchemy e pydantic-settings, e
    chi seguiva il README otteneva un'installazione che non partiva. Un
    elenco che va tenuto allineato a mano prima o poi non lo e' piu'.
    """
    righe = (RADICE / "requirements.txt").read_text(encoding="utf-8").splitlines()
    dichiarate = [r.strip() for r in righe if r.strip() and not r.strip().startswith("#")]
    assert dichiarate == ["-e ."], (
        "requirements.txt elenca dipendenze per conto suo: "
        f"{dichiarate}. Devono stare solo in pyproject.toml"
    )


# ------------------------------- il controllo che impedisce il ripetersi
#
# I test qui sopra elencano difetti trovati uno per uno. Questo cerca la
# categoria: un'opzione esposta che nessuna riga legge. Sono le peggiori,
# perche' non producono un errore ma silenzio, e chi le usa da' la colpa a
# se stesso.


def _campi_di_configurazione() -> list[str]:
    """Ogni foglia di `AppConfig`, con il suo percorso: `security.auth_enabled`."""
    from pydantic import BaseModel

    from shinra.config.settings import AppConfig

    def scendi(modello, prefisso=""):
        for nome, campo in modello.model_fields.items():
            tipo = campo.annotation
            if isinstance(tipo, type) and issubclass(tipo, BaseModel):
                yield from scendi(tipo, f"{prefisso}{nome}.")
            else:
                yield prefisso + nome

    return sorted(scendi(AppConfig))


def test_ogni_opzione_di_configurazione_ha_un_consumatore():
    """Un'opzione che nessuno legge e' una promessa che il programma non mantiene.

    Si cerca il percorso completo — `security.auth_enabled`, non
    `auth_enabled` — perche' cercare solo il nome della foglia lascerebbe
    passare qualunque campo chiamato `enabled`, e sarebbe un controllo che
    si dichiara soddisfatto per omonimia.

    Quando ha girato per la prima volta ne ha trovate due che nessun elenco
    scritto a mano aveva notato: `assistant.language`, mai letta da nessuna
    riga, e `security.protect_dashboard`, che aveva perfino una casella nelle
    impostazioni mentre la rotta rispondeva `True` fisso. Quella prometteva
    di poter *disattivare* la protezione della dashboard, cioe' di riaprire
    un difetto di sicurezza gia' chiuso. Entrambe sono state tolte: il
    linguaggio tornera' con la internazionalizzazione (issue #36), che e' il
    lavoro che lo rendera' vero.

    Se aggiungi un'opzione e questo test diventa rosso, la scelta e' fra
    collegarla e non aggiungerla. Non fra collegarla e allungare un elenco di
    eccezioni.
    """
    sorgenti = [
        p
        for p in (RADICE / "src" / "shinra").rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "settings.py"
    ]
    testo = "\n".join(p.read_text(encoding="utf-8") for p in sorgenti)

    campi = _campi_di_configurazione()
    assert campi, "nessun campo trovato: il test non guarda piu' niente"

    orfani = [c for c in campi if c not in testo]

    assert orfani == [], (
        "queste opzioni sono esposte nella configurazione e nessuna riga di " f"codice le legge: {orfani}"
    )


# ------------------------------------ e il README dice cose che sono ancora vere


def _blocco_yaml_del_readme() -> str:
    """Il blocco di configurazione mostrato nel README dei parametri."""
    testo = (RADICE / "README.md").read_text(encoding="utf-8")
    inizio = testo.index("## ⚙️ Parametri di Configurazione")
    blocco = testo[inizio:]
    apertura = blocco.index("```yaml") + len("```yaml")
    return blocco[apertura : blocco.index("```", apertura)]


def test_il_readme_documenta_chiavi_che_esistono():
    """Il README mostrava una configurazione che non esisteva piu'.

    Alla #38 quel blocco dichiarava `llm.provider` e `llm.base_url` — il primo
    mai esistito, il secondo rinominato in `ollama_url` — e metteva il token di
    Home Assistant dentro `config.yaml`, da dove la #7 lo aveva tolto apposta.
    Chi copiava quel blocco si ritrovava chiavi ignorate in silenzio e un
    segreto nel posto sbagliato.

    Scrivendo la riparazione ho sbagliato a mia volta una chiave — `voce.
    trascrizione` invece di `voce.motore` — che e' la ragione per cui questo
    test esiste invece di una rilettura attenta.
    """
    import yaml

    from shinra.config.settings import AppConfig

    documentato = yaml.safe_load(_blocco_yaml_del_readme())
    vero = AppConfig().model_dump()

    sconosciute = []
    for sezione, campi in documentato.items():
        if sezione not in vero:
            sconosciute.append(sezione)
            continue
        if not isinstance(campi, dict):
            continue
        for campo in campi:
            if campo not in (vero[sezione] or {}):
                sconosciute.append(f"{sezione}.{campo}")

    assert not sconosciute, (
        f"il README documenta chiavi che la configurazione non ha: {sconosciute}. "
        "Chi le copia si ritrova impostazioni ignorate in silenzio."
    )


def test_il_readme_non_invita_a_mettere_segreti_nella_configurazione():
    """Il blocco mostrava `token: \"INSERISCI_QUI_IL_TUO_...\"`.

    I segreti vivono in `.env` dalla #7, e `migra_segreti_su_env()` li sposta
    da `config.yaml` al primo avvio proprio perche' li' non devono stare. Un
    README che invita a scriverceli rimette in circolo il difetto che quella
    issue ha chiuso: `config.yaml` e' finito in un commit una volta.
    """
    from shinra.config import secrets as segreti
    from shinra.config.settings import AppConfig

    documentato = __import__("yaml").safe_load(_blocco_yaml_del_readme())
    vero = AppConfig().model_dump()  # noqa: F841 — serve solo a far fallire prima se il README e' rotto

    for sezione, campo in segreti.CAMPI_SEGRETI:
        valore = (documentato.get(sezione) or {}).get(campo)
        assert valore is None, (
            f"il README mostra {sezione}.{campo} dentro config.yaml: " "e' un segreto e va in .env."
        )


def test_il_modello_del_readme_e_quello_che_si_configura():
    """Il README diceva di scaricare un modello, il codice ne configurava un altro.

    In quattro punti il README consiglia `qwen2.5:3b` — e lo fa con un
    argomento tecnico, il supporto nativo ai tool, che per questo progetto e'
    tutto. Il predefinito nel codice era `gemma2:9b`. Chi seguiva le
    istruzioni scaricava un modello e ne configurava un altro: la chat non
    rispondeva, e il motivo non compariva da nessuna parte.
    """
    import re

    import yaml

    from shinra.config.settings import AppConfig

    testo = (RADICE / "README.md").read_text(encoding="utf-8")
    scaricati = re.findall(r"ollama pull ([^\s`]+)", testo)
    assert scaricati, "il README non dice piu' quale modello scaricare"

    esempio = yaml.safe_load((RADICE / "config" / "config.example.yaml").read_text(encoding="utf-8"))
    predefinito = AppConfig().llm.model

    for modello in scaricati:
        assert modello == predefinito, (
            f"il README dice di scaricare «{modello}» ma il predefinito e' "
            f"«{predefinito}»: chi segue le istruzioni configura un modello che non ha"
        )
    assert (
        esempio["llm"]["model"] == predefinito
    ), f"config.example.yaml dice «{esempio['llm']['model']}» e il codice «{predefinito}»"


# ------------------------------------------------ e il nome dell'immagine e' uno


def _nome_del_deposito() -> str:
    """`ShiniHouse/Shinra`, preso da dove e' dichiarato una volta sola.

    Si legge con un'espressione regolare e non con `tomllib`, che esiste solo
    da Python 3.11: il progetto dichiara 3.10 e la CI lo prova davvero. Una
    riga sola da cercare non vale una dipendenza in piu'.
    """
    import re

    testo = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    trovato = re.search(r'^Repository\s*=\s*"([^"]+)"', testo, re.M)
    assert trovato, "pyproject.toml non dichiara piu' l'indirizzo del deposito"
    return trovato.group(1).removeprefix("https://github.com/").strip("/")


def test_l_immagine_pubblicata_e_quella_che_il_compose_scarica():
    """Il workflow pubblica `ghcr.io/<deposito>`; il compose ne scarica una.

    Devono essere la stessa, e nessuno se ne accorgerebbe se smettessero di
    esserlo: `docker compose pull` fallirebbe con un «not found» in casa di
    chi ha seguito il README, mentre qui tutto sarebbe verde.

    Il workflow costruisce il nome da `github.repository`, che qui non si puo'
    risolvere: si confronta allora con il deposito dichiarato in
    `pyproject.toml`, che e' l'unico posto dove quel nome e' scritto a mano.
    """
    import re

    deposito = _nome_del_deposito().lower()
    atteso = f"ghcr.io/{deposito}"

    trovati = []
    for percorso in (RADICE / "docker-compose.yml", RADICE / "README.md"):
        for riferimento in re.findall(r"ghcr\.io/[a-zA-Z0-9._/-]+", percorso.read_text(encoding="utf-8")):
            # L'etichetta dopo i due punti non conta: qui si guarda il nome.
            trovati.append((percorso.name, riferimento.split(":")[0].lower()))

    assert trovati, "nessuno scarica piu' l'immagine pubblicata: il compose la nomina ancora?"
    for dove, nome in trovati:
        assert nome == atteso, f"{dove} punta a «{nome}», ma si pubblica «{atteso}»"


def test_il_workflow_di_pubblicazione_costruisce_le_due_architetture():
    """Il criterio di accettazione della #37 nomina il Raspberry Pi.

    Un workflow che pubblica solo amd64 lascerebbe fuori ogni Pi e ogni Mac
    con Apple Silicon, e lo farebbe in silenzio: `docker pull` su arm64
    risponde «no matching manifest», che non dice a nessuno di cosa si tratta.
    """
    import yaml

    workflow = yaml.safe_load((RADICE / ".github" / "workflows" / "pubblica.yml").read_text(encoding="utf-8"))
    passi = workflow["jobs"]["pubblica"]["steps"]
    spinta = [p for p in passi if "build-push-action" in str(p.get("uses", ""))]
    assert len(spinta) == 1, "il passo che pubblica non e' piu' uno solo"

    piattaforme = spinta[0]["with"]["platforms"]
    for architettura in ("linux/amd64", "linux/arm64"):
        assert architettura in piattaforme, f"{architettura} non viene piu' pubblicata: {piattaforme}"
