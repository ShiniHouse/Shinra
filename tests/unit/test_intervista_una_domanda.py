"""#209: una domanda per volta, e niente domande su cio' che la casa gia' sa.

Prima di questa scheda ogni passo faceva tre domande in una e chiedeva anche
«chi vive qui?» a una casa con quattro profili. I due difetti si vedono solo
parlandoci: qui si fissano sui testi e sui dati, senza il modello.
"""

import pytest

import shinra.services.interview_engine as modulo
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_noto import cosa_si_sa
from shinra.services.intervista_passi import INTERVIEW_STEPS

VUOTA = {"profili": [], "stanze": [], "fatti": []}


def _passo(identificativo: str) -> dict:
    return next(p for p in INTERVIEW_STEPS if p["id"] == identificativo)


# ------------------------------------------------- una domanda per volta


def test_ogni_passo_ha_una_sola_domanda() -> None:
    """Un punto interrogativo, non tre domande nella stessa frase."""
    piu_di_una = [p["id"] for p in INTERVIEW_STEPS if p["question"].count("?") != 1]
    assert piu_di_una == [], f"passi con piu' (o meno) di una domanda: {piu_di_una}"


def test_nessuna_domanda_elenca_cose_diverse() -> None:
    """Il punto interrogativo non basta: «dove, a che piano e quante stanze?»
    ne ha uno solo e sono tre domande. Si guarda anche l'elenco con le virgole."""
    con_elenco = [p["id"] for p in INTERVIEW_STEPS if p["question"].count(",") >= 2]
    assert con_elenco == [], f"domande che sembrano un elenco: {con_elenco}"


def test_gli_identificativi_dei_passi_sono_unici() -> None:
    ids = [p["id"] for p in INTERVIEW_STEPS]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------- cio' che la casa sa


def test_con_una_casa_vuota_non_si_salta_niente() -> None:
    assert [p["id"] for p in INTERVIEW_STEPS if cosa_si_sa(p, VUOTA)] == []


def test_i_profili_gia_registrati_saltano_chi_vive_qui() -> None:
    dati = {**VUOTA, "profili": ["Alessio", "Sonia", "Thomas"]}
    noto = cosa_si_sa(_passo("famiglia_chi"), dati)
    assert noto and "Alessio, Sonia e Thomas" in noto


def test_un_solo_profilo_non_basta_a_dire_chi_vive_qui() -> None:
    """Chi sta rispondendo e' un profilo: da solo non dice chi altro c'e'."""
    assert cosa_si_sa(_passo("famiglia_chi"), {**VUOTA, "profili": ["Alessio"]}) is None


def test_le_stanze_degli_alias_saltano_la_domanda_sulle_stanze() -> None:
    dati = {**VUOTA, "stanze": ["cucina", "salotto"]}
    noto = cosa_si_sa(_passo("casa_stanze"), dati)
    assert noto and "cucina e salotto" in noto


def test_un_fatto_della_stessa_categoria_con_la_parola_giusta_salta_la_domanda() -> None:
    fatti = [{"text": "La rete ospiti è CasaMia_Guest", "category": "casa_tecnica", "enabled": True}]
    assert cosa_si_sa(_passo("tecnico_wifi"), {**VUOTA, "fatti": fatti})


def test_lo_stesso_fatto_in_un_altra_categoria_non_salta() -> None:
    fatti = [{"text": "La rete ospiti è CasaMia_Guest", "category": "abitudini"}]
    assert cosa_si_sa(_passo("tecnico_wifi"), {**VUOTA, "fatti": fatti}) is None


def test_gli_accenti_non_cambiano_la_risposta() -> None:
    fatti = [{"text": "Vivo nella CITTÀ di Arezzo", "category": "casa"}]
    assert cosa_si_sa(_passo("casa_citta"), {**VUOTA, "fatti": fatti})


# ------------------------------------------- dentro l'intervista, per intero


def _motore(monkeypatch, dati: dict) -> LearningInterviewEngine:
    monkeypatch.setattr(modulo, "dati_della_casa", lambda _store: dati)
    return LearningInterviewEngine()


def test_l_intervista_non_apre_con_una_domanda_che_la_casa_sa(monkeypatch) -> None:
    fatti = [{"text": "Vivo ad Arezzo", "category": "casa", "enabled": True}]
    motore = _motore(monkeypatch, {**VUOTA, "fatti": fatti})

    avvio = motore.start_session("prova")

    assert avvio["step"]["id"] == "casa_piano", "ha rifatto la domanda sulla citta'"
    assert "Arezzo" in avvio["message"], "non dice cosa ha saltato e perche'"
    assert "una per volta" in avvio["message"]


def test_con_una_casa_vuota_la_prima_domanda_e_la_prima(monkeypatch) -> None:
    motore = _motore(monkeypatch, VUOTA)
    assert motore.start_session("prova")["step"]["id"] == INTERVIEW_STEPS[0]["id"]


@pytest.mark.asyncio
async def test_dopo_una_risposta_si_salta_il_passo_che_la_casa_sa(monkeypatch) -> None:
    """Il salto vale anche in mezzo all'intervista, non solo all'inizio."""
    dati = {**VUOTA, "profili": ["Alessio", "Sonia"], "stanze": ["cucina", "salotto"]}
    motore = _motore(monkeypatch, dati)
    motore.start_session("prova")
    # Si porta l'intervista a casa_piano, il passo prima di casa_stanze.
    motore.get_session("prova")["current_step_index"] = INTERVIEW_STEPS.index(_passo("casa_piano"))

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": [{"text": "Abita al terzo livello"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    monkeypatch.setattr(modulo.data_store, "add_knowledge_item", lambda **k: {"text": k["text"]})

    await motore.process_answer("prova", "Al terzo")
    esito = await motore.process_answer("prova", "sì")

    # casa_stanze e famiglia_chi sono noti: si arriva a famiglia_stanze.
    assert esito["step"]["id"] == "famiglia_stanze"
    assert "Conosco gia' queste stanze" in esito["message"]
    assert "In casa ci sono gia' Alessio e Sonia" in esito["message"]


def test_se_la_casa_sa_quasi_tutto_restano_solo_le_domande_aperte(monkeypatch) -> None:
    """Cio' che non si puo' sapere dal database (le domande aperte) si chiede sempre."""
    fatti = []
    for p in INTERVIEW_STEPS:
        parola = (p.get("parole") or ("x",))[0]
        fatti.append({"text": f"Nota con {parola}", "category": p["category"], "enabled": True})
    dati = {"profili": ["Alessio", "Sonia"], "stanze": ["cucina", "salotto"], "fatti": fatti}
    # Le domande aperte, senza `parole` ne' `noto`, non si possono sapere gia'.
    aperte = [p["id"] for p in INTERVIEW_STEPS if not p.get("parole") and not p.get("noto")]
    motore = _motore(monkeypatch, dati)

    avvio = motore.start_session("prova")

    assert aperte, "se non ci sono domande aperte il test non prova piu' niente"
    assert avvio["is_active"] is True
    assert avvio["step"]["id"] == aperte[0]


@pytest.mark.asyncio
async def test_una_risposta_povera_produce_un_solo_approfondimento(monkeypatch) -> None:
    """Si chiede di approfondire una volta, poi si passa oltre: niente ciclo."""
    motore = _motore(monkeypatch, VUOTA)
    motore.start_session("prova")

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": []}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    monkeypatch.setattr(modulo.data_store, "add_knowledge_item", lambda **k: {"text": k["text"]})

    primo = await motore.process_answer("prova", "boh, non saprei")
    secondo = await motore.process_answer("prova", "non so davvero")

    assert primo["step"]["id"] == INTERVIEW_STEPS[0]["id"], "non ha insistito"
    assert "una volta sola" in primo["message"]
    assert secondo["step"]["id"] == INTERVIEW_STEPS[1]["id"], "ha insistito una seconda volta"
