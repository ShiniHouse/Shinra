"""La Modalita' Apprendimento deve arrivare in fondo.

Era la funzione piu' recente del progetto e non aveva mai completato un passo:
`interview_engine` chiamava due metodi inesistenti — `add_knowledge_item` su
DataStore e `generate` su OllamaClient. Il primo produceva un 500 a ogni
risposta; il secondo, catturato, faceva cadere sempre nel ripiego, rendendo
codice morto il prompt di estrazione.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shinra.infra.data_store import DataStore
from shinra.infra.db import importazione
from shinra.infra.llm.ollama import OllamaClient
from shinra.services.interview_engine import (
    INTERVIEW_STEPS,
    LIMITE_CORREZIONI,
    LearningInterviewEngine,
    _e_affermativa,
    _e_negativa,
)

RADICE = Path(__file__).resolve().parent.parent.parent


@pytest.fixture()
def archivio(tmp_path) -> DataStore:
    """Un database vuoto: i test non toccano la conoscenza vera della casa."""
    importazione.crea_vuoto(tmp_path / "shinra.db")
    yield DataStore()


# ------------------------------------------------------------------- BLK-01


def test_aggiunge_un_fatto(archivio: DataStore) -> None:
    salvato = archivio.add_knowledge_item("La sveglia nei feriali e' alle 7:00", "abitudini")
    assert salvato["text"] == "La sveglia nei feriali e' alle 7:00"
    assert salvato["category"] == "abitudini"
    assert salvato["enabled"] is True
    assert salvato["id"]
    assert archivio.get_knowledge() == [salvato]


def test_non_duplica_un_fatto_gia_presente(archivio: DataStore) -> None:
    """Durante un'intervista capita di ripetersi, e ogni fatto finisce nel
    prompt di sistema: i doppioni si pagano a ogni risposta."""
    primo = archivio.add_knowledge_item("Il contatore e' nel sottoscala")
    secondo = archivio.add_knowledge_item("  il contatore E' NEL SOTTOSCALA  ")
    assert primo["id"] == secondo["id"]
    assert len(archivio.get_knowledge()) == 1


def test_gli_identificativi_restano_unici_dopo_una_cancellazione(archivio: DataStore) -> None:
    """Con identificativi basati sul conteggio, cancellare un fatto e
    aggiungerne un altro produce un identificativo gia' usato: modificare il
    nuovo sovrascriverebbe un fatto diverso."""
    a = archivio.add_knowledge_item("Primo fatto")
    b = archivio.add_knowledge_item("Secondo fatto")
    archivio.save_knowledge([f for f in archivio.get_knowledge() if f["id"] != a["id"]])
    c = archivio.add_knowledge_item("Terzo fatto")
    assert len({a["id"], b["id"], c["id"]}) == 3


def test_un_fatto_vuoto_viene_rifiutato(archivio: DataStore) -> None:
    with pytest.raises(ValueError):
        archivio.add_knowledge_item("   ")


# ------------------------------------------------------------------- BLK-02


@pytest.mark.asyncio
async def test_estrae_i_fatti_dalla_risposta(monkeypatch) -> None:
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {
            "facts": [
                {"text": "La sveglia nei feriali e' alle 7:00", "category": "abitudini"},
                {"text": "Al risveglio si accende la luce in cucina", "category": "abitudini"},
            ],
            "proposed_routine": {
                "name": "Buongiorno",
                "trigger_phrases": ["buongiorno"],
                "actions": [{"type": "ha_device", "entity_id": "light.cucina", "action": "turn_on"}],
            },
        }

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    esito = await motore._extract_knowledge_and_routines(INTERVIEW_STEPS[2], "Mi sveglio alle 7")

    assert len(esito["facts"]) == 2
    assert esito["proposed_routine"]["name"] == "Buongiorno"


@pytest.mark.asyncio
async def test_con_ollama_spento_la_risposta_non_va_persa(monkeypatch) -> None:
    """Meglio conservare la frase dell'utente non elaborata che perderla."""
    motore = LearningInterviewEngine()

    async def spento(prompt, system="", temperature=0.1):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", spento)
    esito = await motore._extract_knowledge_and_routines(INTERVIEW_STEPS[0], "Vivo ad Arezzo")
    assert esito["facts"][0]["text"] == "Vivo ad Arezzo"
    assert esito["proposed_routine"] is None


@pytest.mark.parametrize(
    "grezzi",
    [None, "non una lista", [None, 123], [{"text": "  "}], [{"senza": "testo"}], [""]],
)
def test_scarta_i_fatti_inutilizzabili(grezzi) -> None:
    """Un modello piccolo restituisce spesso stringhe o campi vuoti: senza
    filtro finirebbero nella conoscenza e da li' nel prompt di ogni risposta."""
    assert LearningInterviewEngine._fatti_validi(grezzi, INTERVIEW_STEPS[0]) == []


def test_accetta_i_fatti_scritti_come_stringhe() -> None:
    fatti = LearningInterviewEngine._fatti_validi(["Vivo ad Arezzo"], INTERVIEW_STEPS[0])
    assert fatti == [{"text": "Vivo ad Arezzo", "category": INTERVIEW_STEPS[0]["category"]}]


@pytest.mark.parametrize("grezza", [None, "testo", {}, {"name": "  "}, {"actions": []}])
def test_scarta_le_routine_senza_nome(grezza) -> None:
    assert LearningInterviewEngine._routine_valida(grezza) is None


def test_una_routine_senza_azioni_resta_proponibile() -> None:
    """Il nome basta: le azioni si scelgono nell'editor prima di confermarla."""
    r = LearningInterviewEngine._routine_valida({"name": "Cinema"})
    assert r["name"] == "Cinema"
    assert r["actions"] == []


# --------------------------------------------------- l'intervista per intero


@pytest.mark.asyncio
async def test_l_intervista_arriva_in_fondo(archivio: DataStore, monkeypatch) -> None:
    """La prova che non era mai riuscita: sei passi, nessun errore.

    Prima di questa correzione la prima risposta sollevava AttributeError e
    l'utente vedeva un 500.
    """
    import shinra.services.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": [{"text": f"Fatto dal passo {len(archivio.get_knowledge())}"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)

    avvio = motore.start_session("prova")
    assert avvio["is_active"] and avvio["step_index"] == 0

    for _ in INTERVIEW_STEPS:
        esito = await motore.process_answer("prova", "Una risposta abbastanza lunga da valere.")
        assert "message" in esito
        # Dalla #170 un passo sono due turni: si risponde, si guarda cosa ha
        # capito, si conferma. Senza il «si'» l'intervista resta ferma qui.
        esito = await motore.process_answer("prova", "sì")
        assert "message" in esito

    assert esito["is_complete"] is True
    assert len(archivio.get_knowledge()) == len(INTERVIEW_STEPS)
    assert not motore.is_session_active("prova")


@pytest.mark.asyncio
async def test_un_fatto_non_salvabile_non_ferma_l_intervista(archivio, monkeypatch) -> None:
    """Era esattamente il difetto BLK-01: l'errore arrivava all'utente come 500."""
    import shinra.services.interview_engine as modulo

    def rifiuta(*a, **k):
        raise OSError("disco pieno")

    monkeypatch.setattr(archivio, "add_knowledge_item", rifiuta)
    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": [{"text": "Un fatto qualsiasi"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    motore.start_session("prova")
    await motore.process_answer("prova", "Una risposta valida.")
    # Il salvataggio avviene alla conferma: e' li' che il disco pieno esplode.
    esito = await motore.process_answer("prova", "sì")
    assert esito["is_active"] is True
    assert esito["new_facts"] == []


# ------------------------------------------------- il JSON che torna davvero


@pytest.mark.asyncio
async def test_json_avvolto_in_un_blocco_di_codice(monkeypatch) -> None:
    """Anche con format=json alcuni modelli aggiungono l'involucro markdown."""
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {"success": True, "content": '```json\n{"facts": []}\n```'}

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") == {"facts": []}


@pytest.mark.asyncio
async def test_json_preceduto_da_una_frase(monkeypatch) -> None:
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {
            "success": True,
            "content": 'Ecco il risultato: {"facts": [{"text": "ciao"}]} spero vada bene',
        }

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") == {"facts": [{"text": "ciao"}]}


@pytest.mark.parametrize("contenuto", ["", "non json affatto", "[1, 2, 3]", "{rotto", "null"])
@pytest.mark.asyncio
async def test_risposte_inutilizzabili_danno_none(monkeypatch, contenuto: str) -> None:
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {"success": True, "content": contenuto}

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") is None


@pytest.mark.asyncio
async def test_ollama_irraggiungibile_da_none(monkeypatch) -> None:
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {"success": False, "error": "connessione rifiutata"}

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") is None


# ------------------------- quando non capisce, deve dirlo (issue #170)


@pytest.mark.asyncio
async def test_quando_il_modello_non_interpreta_l_intervista_lo_dice(archivio, monkeypatch) -> None:
    """Il difetto della #170, ed e' peggio del silenzio.

    Il ripiego che conserva la frase grezza produce un fatto come tutti gli
    altri. Il messaggio contava i fatti e rispondeva «Ricevuto! Ho aggiunto 1
    nuovi dettagli alla mia conoscenza»: falliva e **rassicurava**.

    In casa e' successo per sei domande di fila, con un modello da un miliardo
    di parametri, e chi stava rispondendo ha creduto per tutto il tempo che la
    casa stesse imparando. Un guasto che si presenta come normalita' costa
    piu' di un guasto che si vede.
    """
    import shinra.services.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def non_capisce(prompt, system="", temperature=0.1):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", non_capisce)

    motore.start_session("prova")
    # La prima volta insiste (#170); alla seconda conserva e lo dichiara.
    await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")
    esito = await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")

    assert esito["interpretato"] is False, "l'esito non dichiara che l'estrazione e' fallita"
    messaggio = esito["message"].lower()
    assert "ricevuto" not in messaggio, "dice «ricevuto» dopo aver fallito"
    assert "non sono riuscita" in messaggio, f"non dice che non ha capito: {esito['message']!r}"
    assert "modello" in messaggio, "non dice dove guardare"

    # E la risposta non va comunque persa: resta conservata cosi' com'e'.
    assert any("Arezzo" in f["text"] for f in archivio.get_knowledge())


@pytest.mark.asyncio
async def test_sei_fallimenti_di_fila_non_si_chiudono_con_ottimo_lavoro(archivio, monkeypatch) -> None:
    """La chiusura e' l'ultima occasione per dire che e' andata male."""
    import shinra.services.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def non_capisce(prompt, system="", temperature=0.1):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", non_capisce)

    motore.start_session("prova")
    for _ in INTERVIEW_STEPS:
        # Due turni per passo: la prima risposta fa insistere, la seconda
        # conserva la frase grezza e passa oltre.
        await motore.process_answer("prova", "Una risposta abbastanza lunga da valere.")
        esito = await motore.process_answer("prova", "Una risposta abbastanza lunga da valere.")

    assert esito["is_complete"] is True
    messaggio = esito["message"].lower()
    assert "ottimo lavoro" not in messaggio, "si congratula dopo sei fallimenti di fila"
    assert str(len(INTERVIEW_STEPS)) in esito["message"], "non dice quante risposte ha mancato"
    assert "non sono riuscita a interpretarle" in messaggio


@pytest.mark.asyncio
async def test_quando_capisce_davvero_lo_dice_come_prima(archivio, monkeypatch) -> None:
    """Il gemello, perche' la riparazione non diventi «si scusa sempre»."""
    import shinra.services.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def capisce(prompt, system="", temperature=0.1):
        return {"facts": [{"text": "La casa e' ad Arezzo"}, {"text": "L'appartamento e' al secondo piano"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", capisce)

    motore.start_session("prova")
    await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")
    esito = await motore.process_answer("prova", "sì")

    assert esito["interpretato"] is True
    assert "Ricevuto" in esito["message"]
    assert "2" in esito["message"], "non dice quanti dettagli ha imparato"
    assert "non sono riuscita" not in esito["message"].lower()


@pytest.mark.asyncio
async def test_una_risposta_da_cui_non_c_e_niente_da_imparare_non_e_un_guasto(archivio, monkeypatch) -> None:
    """Terzo caso, diverso dagli altri due: il modello ha capito benissimo, e
    da «boh» non c'era niente da ricavare. Non va raccontato come un
    fallimento del modello, o si manda a cercare dalla parte sbagliata."""
    import shinra.services.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def niente_da_dire(prompt, system="", temperature=0.1):
        return {"facts": []}

    monkeypatch.setattr(motore.ollama, "genera_json", niente_da_dire)

    motore.start_session("prova")
    # Prima insiste: «boh» e' esattamente la risposta su cui vale la pena
    # insistere. Poi passa oltre, e nemmeno li' accusa il modello.
    primo = await motore.process_answer("prova", "boh")
    esito = await motore.process_answer("prova", "boh")

    for passaggio in (primo, esito):
        assert passaggio["interpretato"] is True, "una risposta vuota non e' un guasto del modello"
        assert (
            "modello" not in passaggio["message"].lower()
        ), "accusa il modello per una risposta che non diceva niente"
    assert "niente da ricordare" in esito["message"].lower()


@pytest.mark.asyncio
async def test_l_avviso_nel_log_dice_quale_modello_ha_fallito(monkeypatch) -> None:
    """Chi legge il journal deve sapere dove guardare.

    In casa il difetto e' stato trovato cosi': cinque «Estrazione non
    riuscita» nel journal. Ma quella riga non diceva **quale** modello stava
    fallendo, e il modello era il difetto — `llama3.2:1b`, un miliardo di
    parametri a cui si chiedeva di produrre JSON strutturato. Il nome nella
    riga accorcia l'indagine da un'ora a un minuto.

    Il logger si sostituisce invece di leggere `caplog`: l'applicazione
    installa i propri gestori. E' la stessa trappola documentata in
    `test_il_testo_detto_non_finisce_nel_log`, e ci sono gia' inciampato tre
    volte.
    """
    import shinra.services.interview_engine as modulo

    scritte: list[str] = []

    class LoggerFinto:
        def warning(self, messaggio, *argomenti):
            scritte.append(messaggio % argomenti if argomenti else messaggio)

        def __getattr__(self, _nome):
            return lambda *a, **k: None

    monkeypatch.setattr(modulo, "logger", LoggerFinto())
    monkeypatch.setattr(modulo.impostazioni.settings.llm, "model", "modello-di-prova:1b")

    motore = LearningInterviewEngine()

    async def non_capisce(prompt, system="", temperature=0.1):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", non_capisce)
    await motore._extract_knowledge_and_routines(INTERVIEW_STEPS[0], "Vivo ad Arezzo")

    assert scritte, "il fallimento non finisce piu' nel log"
    detto = "\n".join(scritte)
    assert "modello-di-prova:1b" in detto, f"l'avviso non dice quale modello ha fallito: {detto!r}"


# ------------------- far vedere cosa ha capito, prima di salvarlo (issue #170)


def _motore(archivio, monkeypatch, risposte):
    """Un motore il cui modello risponde con `risposte`, una per chiamata.

    L'ultima si ripete all'infinito: quasi tutti i test qui sotto fanno due o
    tre turni e vogliono lo stesso comportamento dopo il primo.
    """
    import shinra.services.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()
    chiamate = {"n": 0}

    async def modello(prompt, system="", temperature=0.1):
        indice = min(chiamate["n"], len(risposte) - 1)
        chiamate["n"] += 1
        return risposte[indice]

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    motore.start_session("prova")
    return motore


CAPITO = {"facts": [{"text": "La casa è ad Arezzo"}, {"text": "L'appartamento è al secondo piano"}]}

# Quante correzioni di fila una persona sopporta prima di chiudere il modale.
# E' questo il contratto che il riepilogo non deve rompere, e sta qui invece
# di leggersi da `LIMITE_CORREZIONI` apposta.
TOLLERANZA_CORREZIONI = 5


@pytest.mark.asyncio
async def test_prima_di_salvare_mostra_cosa_ha_capito(archivio, monkeypatch) -> None:
    """Il difetto peggiore della #170, perche' non si vede mai.

    L'intervista salvava e proseguiva: un'interpretazione sbagliata diventava
    conoscenza permanente in silenzio, e la si scopriva mesi dopo da una
    risposta strana in cucina — senza sapere da dove venisse.

    Adesso il passo si ferma e fa vedere. Il test controlla le due meta' della
    stessa cosa: che il riepilogo dica i fatti, e che il database sia ancora
    vuoto.
    """
    motore = _motore(archivio, monkeypatch, [CAPITO])
    esito = await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")

    assert esito["fase"] == "conferma"
    assert esito["is_complete"] is False
    assert esito["step_index"] == 0, "e' passato alla domanda dopo senza chiedere niente"
    for fatto in CAPITO["facts"]:
        assert fatto["text"] in esito["message"], f"il riepilogo non dice «{fatto['text']}»"
    assert [f["text"] for f in esito["capiti"]] == [f["text"] for f in CAPITO["facts"]]
    assert esito["new_facts"] == [], "dichiara di aver salvato prima di aver chiesto"
    assert archivio.get_knowledge() == [], "ha salvato senza chiedere"
    assert esito["suggerimento"], "non dice come si risponde a un riepilogo"


@pytest.mark.asyncio
async def test_un_si_salva_quello_che_aveva_capito(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch, [CAPITO])
    await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")
    esito = await motore.process_answer("prova", "sì")

    assert esito["fase"] == "domanda"
    assert esito["step_index"] == 1, "non e' passato alla domanda successiva"
    salvati = [f["text"] for f in archivio.get_knowledge()]
    assert salvati == [f["text"] for f in CAPITO["facts"]]
    assert [f["text"] for f in esito["new_facts"]] == salvati


@pytest.mark.asyncio
async def test_un_no_non_salva_niente_e_prosegue(archivio, monkeypatch) -> None:
    """Poter dire di no e' cio' che rende la conferma una conferma.

    Senza questa uscita il riepilogo sarebbe solo un passaggio in piu' da
    accettare, e si imparerebbe a rispondere «si'» senza leggere.
    """
    motore = _motore(archivio, monkeypatch, [CAPITO])
    await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")
    esito = await motore.process_answer("prova", "no")

    assert archivio.get_knowledge() == [], "ha salvato lo stesso dopo un «no»"
    assert esito["step_index"] == 1, "un «no» blocca l'intervista invece di farla proseguire"
    assert esito["new_facts"] == []


@pytest.mark.asyncio
async def test_una_correzione_sostituisce_cio_che_aveva_capito(archivio, monkeypatch) -> None:
    """Correggere deve **cambiare** cio' che si salva, non aggiungersi.

    Se la correzione si limitasse a passare oltre, il riepilogo sarebbe una
    formalita': si vedrebbe l'errore e non si potrebbe farci niente.
    """
    corretto = {"facts": [{"text": "La casa è a Siena"}]}
    motore = _motore(archivio, monkeypatch, [CAPITO, corretto])

    await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")
    riepilogo = await motore.process_answer("prova", "No, veramente vivo a Siena")
    assert riepilogo["fase"] == "conferma", "una correzione non torna a farsi confermare"
    assert "Siena" in riepilogo["message"]
    assert archivio.get_knowledge() == [], "ha salvato la correzione senza richiedere conferma"

    await motore.process_answer("prova", "sì")
    salvati = [f["text"] for f in archivio.get_knowledge()]
    assert salvati == ["La casa è a Siena"], f"ha salvato anche cio' che era sbagliato: {salvati}"


@pytest.mark.asyncio
async def test_non_si_corregge_all_infinito(archivio, monkeypatch) -> None:
    """Ogni testo libero e' una correzione, e ogni correzione riapre la
    conferma: senza un limite, chi non risponde mai «si'» resta fermo sul
    primo passo per sempre e abbandona l'intervista a meta'."""
    motore = _motore(archivio, monkeypatch, [CAPITO])
    await motore.process_answer("prova", "Vivo ad Arezzo al secondo piano")

    # Il numero di giri non si legge da `LIMITE_CORREZIONI`: un test che
    # prende dalla costante il proprio limite si muove insieme a lei, e
    # portarla a novemila lo lascia verde. E' successo, alla prima mutazione
    # di questa riga. TOLLERANZA_CORREZIONI e' quanto sopporta una persona
    # prima di chiudere il modale, e quello e' il vero contratto.
    for tentativo in range(TOLLERANZA_CORREZIONI):
        esito = await motore.process_answer("prova", f"No, veramente sto in centro {tentativo}")
        if esito["step_index"] == 1:
            break
    else:
        raise AssertionError(
            f"dopo {TOLLERANZA_CORREZIONI} correzioni l'intervista e' ancora "
            "ferma sullo stesso passo: chi risponde non ne esce piu'"
        )

    assert archivio.get_knowledge(), "non ha salvato niente nemmeno dopo aver rinunciato"
    assert LIMITE_CORREZIONI < TOLLERANZA_CORREZIONI, (
        f"il limite delle correzioni e' salito a {LIMITE_CORREZIONI}: "
        "oltre qualche giro il riepilogo diventa una trappola"
    )


@pytest.mark.asyncio
async def test_insiste_una_volta_sola_su_una_risposta_povera(archivio, monkeypatch) -> None:
    """Prima una risposta di due parole veniva accettata e si passava oltre:
    la domanda non tornava piu', e quel pezzo di casa restava ignoto per
    sempre. Si insiste una volta — e **una sola**, perche' un'intervista che
    non accetta un «boh» la si abbandona a meta'."""
    motore = _motore(archivio, monkeypatch, [{"facts": []}])

    primo = await motore.process_answer("prova", "boh")
    assert primo["step_index"] == 0, "accetta una risposta vuota e passa oltre"
    assert INTERVIEW_STEPS[0]["question"] in primo["message"], "insiste senza ripetere la domanda"

    secondo = await motore.process_answer("prova", "boh anche adesso")
    assert secondo["step_index"] == 1, "insiste una seconda volta sulla stessa domanda"


@pytest.mark.asyncio
async def test_l_insistenza_porta_un_esempio_concreto(archivio, monkeypatch) -> None:
    """«Dimmi qualcosa di piu'» non aiuta nessuno: chi non sapeva cosa dire
    la prima volta non lo sa nemmeno la seconda. L'esempio e' il suggerimento
    gia' scritto nel passo, senza il «es.» che li' serviva alla schermata."""
    motore = _motore(archivio, monkeypatch, [{"facts": []}])
    esito = await motore.process_answer("prova", "boh")

    esempio = INTERVIEW_STEPS[0]["hint"].removeprefix("es. ")
    assert esempio in esito["message"], f"l'insistenza non porta un esempio: {esito['message']!r}"
    assert "es. " not in esito["message"], "l'esempio si porta dietro l'abbreviazione della schermata"


@pytest.mark.parametrize("detto", ["sì", "Sì!", "si", "SI", "ok", "Va bene.", "esatto", "Certo!", "confermo"])
def test_si_detto_in_tutti_i_modi_in_cui_si_dice(detto: str) -> None:
    """Chi conferma scrive «Sì!», «ok», «va bene»: un confronto con la sola
    stringa «si» manderebbe tutto il resto sul ramo delle correzioni, e il
    passo non si chiuderebbe mai."""
    assert _e_affermativa(detto), f"«{detto}» non viene letto come un si'"
    assert not _e_negativa(detto)


@pytest.mark.parametrize("detto", ["no", "No.", "NO", "sbagliato", "lascia perdere", "annulla"])
def test_no_detto_in_tutti_i_modi_in_cui_si_dice(detto: str) -> None:
    assert _e_negativa(detto), f"«{detto}» non viene letto come un no"
    assert not _e_affermativa(detto)


@pytest.mark.parametrize(
    "detto",
    [
        "No, veramente vivo a Siena",
        "sì ma il piano è il terzo",
        "Vivo ad Arezzo",
        "",
    ],
)
def test_una_frase_intera_non_e_un_si_ne_un_no(detto: str) -> None:
    """Il rischio opposto, e piu' costoso: «sì ma il piano è il terzo» letto
    come un «sì» salverebbe il piano sbagliato **e** direbbe di aver capito.
    Sono correzioni, e come tali vanno trattate."""
    assert not _e_affermativa(detto)
    assert not _e_negativa(detto)
