"""Il banco di prova del tool calling misura quello che dice di misurare (issue #183).

Il banco (`scripts/banco_tool_calling.py`) gira sulla macchina di casa, contro
un Ollama vero: non si puo' eseguire in CI. Ma un banco che sbaglia a contare e'
peggio di nessun banco — produrrebbe numeri sicuri e falsi, e su quei numeri si
deciderebbe l'architettura della `0.6.0`. Quindi qui si prova tutto quello che
si puo' provare senza Ollama:

- **il corpus e' valido**: ogni strumento atteso esiste, ogni argomento atteso e'
  un parametro vero, ogni valore enumerato e' ammesso;
- **il punteggio e' giusto**, nei casi che contano (un `entity_id` inventato, una
  frase ambigua in cui indovinare e' sbagliato, l'ordine delle chiamate);
- **il ciclo e' quello dell'agente**: gli strumenti solo se la frase li chiama e
  solo al primo giro, il rilevamento del contesto troncato, i cicli, gli errori —
  contro un Ollama finto.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest
import yaml

from shinra.skills.registry import TOOLS_SCHEMA

RADICE = Path(__file__).resolve().parent.parent.parent
CORPUS = RADICE / "banco" / "corpus.yaml"
MONDO = RADICE / "banco" / "mondo.yaml"

CATEGORIE = {
    "casa",
    "clima",
    "tapparelle",
    "sicurezza",
    "dispositivi",
    "informazioni",
    "energia",
    "agenda",
    "promemoria",
    "conversazione",
    "ambigua",
    "sconosciuta",
    "piu_passaggi",
    "sicurezza_del_modello",
}


@pytest.fixture(scope="module")
def banco():
    spec = importlib.util.spec_from_file_location(
        "banco_tool_calling", RADICE / "scripts" / "banco_tool_calling.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    # I `dataclass` cercano il loro modulo in `sys.modules`: un modulo caricato da un
    # percorso non ci sta, se non lo si mette.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def voci():
    return yaml.safe_load(CORPUS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def mondo(banco):
    return banco.Mondo.carica()


def _parametri():
    return {s["function"]["name"]: s["function"]["parameters"] for s in TOOLS_SCHEMA}


# ------------------------------------------------------------ il corpus


def test_il_corpus_e_abbastanza_grande_e_ogni_categoria_e_rappresentata(voci):
    assert len(voci) >= 50, f"richieste nel corpus: {len(voci)}"
    per_categoria = {}
    for v in voci:
        per_categoria[v["categoria"]] = per_categoria.get(v["categoria"], 0) + 1

    assert set(per_categoria) <= CATEGORIE, f"categorie sconosciute: {set(per_categoria) - CATEGORIE}"
    scoperte = [c for c in CATEGORIE if per_categoria.get(c, 0) < 2]
    assert scoperte == [], f"categorie con meno di due richieste: {scoperte}"
    assert per_categoria["piu_passaggi"] >= 4, "servono richieste a piu' passaggi: e' la scommessa della fase"


def test_gli_identificativi_sono_unici_e_le_frasi_non_si_ripetono(voci):
    ids = [v["id"] for v in voci]
    frasi = [v["frase"].strip().casefold() for v in voci]

    assert len(ids) == len(set(ids)), "identificativi ripetuti"
    assert len(frasi) == len(set(frasi)), "frasi ripetute: la stessa prova conta due volte"


def test_ogni_strumento_atteso_esiste_e_ogni_argomento_e_un_suo_parametro(voci):
    parametri = _parametri()
    problemi = []
    for v in voci:
        for attesa in v.get("attesi") or []:
            nome = attesa["tool"]
            if nome not in parametri:
                problemi.append(f"{v['id']}: lo strumento «{nome}» non esiste")
                continue
            proprieta = parametri[nome].get("properties", {})
            for chiave, valore in (attesa.get("args") or {}).items():
                if chiave not in proprieta:
                    problemi.append(f"{v['id']}: «{chiave}» non e' un parametro di {nome}")
                    continue
                ammessi = proprieta[chiave].get("enum")
                if ammessi and isinstance(valore, str) and valore not in ammessi:
                    problemi.append(
                        f"{v['id']}: «{valore}» non e' un valore ammesso per {nome}.{chiave} ({ammessi})"
                    )
                if ammessi and isinstance(valore, dict) and "una_di" in valore:
                    fuori = [x for x in valore["una_di"] if x not in ammessi]
                    if fuori:
                        problemi.append(f"{v['id']}: {fuori} non sono valori ammessi per {nome}.{chiave}")

    assert problemi == [], "\n".join(problemi)


def test_gli_argomenti_obbligatori_di_uno_strumento_sono_tutti_attesi_o_non_verificabili(voci):
    """Se un parametro obbligatorio non e' fra quelli attesi, il banco darebbe per
    buona una chiamata a cui manca. Si ammette solo per i testi liberi."""
    parametri = _parametri()
    liberi = {"query", "text", "location", "voce", "titolo", "quando_detto", "mode_name"}
    mancano = []
    for v in voci:
        for attesa in v.get("attesi") or []:
            richiesti = set(parametri[attesa["tool"]].get("required", []))
            presenti = set((attesa.get("args") or {}).keys())
            scoperti = richiesti - presenti - liberi
            if scoperti:
                mancano.append(f"{v['id']}: {attesa['tool']} non verifica {sorted(scoperti)}")

    assert mancano == [], "\n".join(mancano)


def test_le_frasi_ambigue_e_sconosciute_non_hanno_uno_strumento_giusto(voci):
    sbagliate = [v["id"] for v in voci if v["categoria"] in ("ambigua", "sconosciuta") and v.get("attesi")]

    assert (
        sbagliate == []
    ), f"in queste frasi indovinare e' sbagliato, non possono attendere uno strumento: {sbagliate}"


# -------------------------------------------------------------- il mondo


def test_ogni_dispositivo_atteso_esiste_nel_mondo(voci, mondo):
    inventati = []
    for v in voci:
        for attesa in v.get("attesi") or []:
            valore = (attesa.get("args") or {}).get("entity_id")
            candidati = valore.get("una_di", []) if isinstance(valore, dict) else [valore]
            inventati += [
                f"{v['id']}: {c}" for c in candidati if isinstance(c, str) and c not in mondo.entita
            ]

    assert inventati == [], f"il corpus attende dispositivi che il mondo non ha: {inventati}"


def test_le_risposte_finte_sono_di_strumenti_veri(mondo):
    nomi = set(_parametri())
    sconosciuti = sorted(set(mondo.dati.get("risposte", {})) - nomi)

    assert sconosciuti == [], f"risposte finte per strumenti che non esistono: {sconosciuti}"


def test_il_prompt_del_banco_e_quello_dell_agente(banco, mondo):
    """Se il banco usasse un prompt suo, misurerebbe un modello che in casa non gira."""
    prompt = banco.prompt_di_sistema(mondo)

    assert prompt.startswith("Sei ") and "REGOLE SUI TOOL" in prompt
    assert "luce cucina" in prompt and "light.cucina" in prompt
    assert "Cinema" in prompt


# ------------------------------------------------------------ il punteggio


@pytest.mark.parametrize(
    ("atteso", "osservato", "esito"),
    [
        ("light.cucina", "light.cucina", True),
        ("light.cucina", " Light.Cucina ", True),
        (22, 22.0, True),
        (22, "22", True),
        (22, 23, False),
        ({"contiene": "verdi"}, "Giuseppe Verdi", True),
        ({"contiene": "verdi"}, "Rossi", False),
        ({"una_di": ["arma_casa", "arma_fuori"]}, "arma_fuori", True),
        ({"una_di": ["arma_casa", "arma_fuori"]}, "disarma", False),
        ({"presente": True}, "blu", True),
        ({"presente": True}, None, False),
        ("x", None, False),
    ],
)
def test_combacia(banco, atteso, osservato, esito):
    assert banco.combacia(atteso, osservato) is esito


def _valuta(banco, mondo, voce, chiamate):
    strumenti = set(_parametri())
    return banco.valuta(voce, [banco.Chiamata(n, a) for n, a in chiamate], mondo.entita, strumenti)


LUCE = {
    "id": "x",
    "categoria": "casa",
    "attesi": [{"tool": "control_device", "args": {"entity_id": "light.cucina", "action": "turn_on"}}],
}


def test_una_chiamata_giusta_e_giusta(banco, mondo):
    esito = _valuta(
        banco, mondo, LUCE, [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]
    )

    assert esito["ok_strumento"] and esito["ok_argomenti"] and not esito["inventate"]


def test_lo_strumento_giusto_con_il_dispositivo_sbagliato_e_uno_strumento_giusto_ma_argomenti_sbagliati(
    banco, mondo
):
    esito = _valuta(
        banco, mondo, LUCE, [("control_device", {"entity_id": "light.salotto", "action": "turn_on"})]
    )

    assert esito["ok_strumento"] is True and esito["ok_argomenti"] is False


def test_uno_strumento_sbagliato_non_e_valutato_negli_argomenti(banco, mondo):
    esito = _valuta(banco, mondo, LUCE, [("get_home_status", {})])

    assert esito["ok_strumento"] is False and esito["ok_argomenti"] is None


def test_un_dispositivo_inventato_si_conta_a_parte(banco, mondo):
    esito = _valuta(
        banco, mondo, LUCE, [("control_device", {"entity_id": "light.cantina", "action": "turn_on"})]
    )

    assert esito["inventate"] == ["light.cantina"]


def test_uno_strumento_inesistente_si_conta_a_parte(banco, mondo):
    esito = _valuta(banco, mondo, LUCE, [("accendi_tutto", {})])

    assert esito["inesistenti"] == ["accendi_tutto"] and esito["ok_strumento"] is False


def test_in_una_frase_ambigua_chiedere_e_giusto_e_indovinare_no(banco, mondo):
    ambigua = {"id": "a", "categoria": "ambigua", "attesi": []}

    assert _valuta(banco, mondo, ambigua, [])["ok_strumento"] is True
    assert (
        _valuta(banco, mondo, ambigua, [("get_home_status", {})])["ok_strumento"] is True
    ), "leggere lo stato non comanda niente: non e' indovinare"
    assert (
        _valuta(
            banco, mondo, ambigua, [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]
        )["ok_strumento"]
        is False
    )


def test_senza_strumenti_attesi_chiamarne_uno_e_sbagliato(banco, mondo):
    saluto = {"id": "s", "categoria": "conversazione", "attesi": []}

    assert _valuta(banco, mondo, saluto, [])["ok_strumento"] is True
    assert _valuta(banco, mondo, saluto, [("get_weather", {"location": "Roma"})])["ok_strumento"] is False


def test_piu_chiamate_con_ordine_libero_non_dipendono_dall_ordine(banco, mondo):
    voce = {
        "id": "m",
        "categoria": "piu_passaggi",
        "ordine": "libero",
        "attesi": [
            {"tool": "comanda_tapparella", "args": {"entity_id": "cover.salotto", "azione": "chiudi"}},
            {"tool": "control_device", "args": {"entity_id": "light.salotto", "action": "turn_on"}},
        ],
    }
    giuste = [
        ("control_device", {"entity_id": "light.salotto", "action": "turn_on"}),
        ("comanda_tapparella", {"entity_id": "cover.salotto", "azione": "chiudi"}),
    ]

    assert _valuta(banco, mondo, voce, giuste)["ok_argomenti"] is True
    assert _valuta(banco, mondo, voce, giuste[:1])["ok_strumento"] is False, "ne manca una"


def test_due_chiamate_uguali_non_soddisfano_due_attese_diverse(banco, mondo):
    voce = {
        "id": "d",
        "categoria": "piu_passaggi",
        "ordine": "libero",
        "attesi": [
            {"tool": "control_device", "args": {"entity_id": "light.salotto", "action": "turn_off"}},
            {"tool": "control_device", "args": {"entity_id": "light.cucina", "action": "turn_off"}},
        ],
    }
    ripetuta = [("control_device", {"entity_id": "light.salotto", "action": "turn_off"})] * 2

    esito = _valuta(banco, mondo, voce, ripetuta)

    assert esito["ok_strumento"] is True and esito["ok_argomenti"] is False


# --------------------------------------------------- il ciclo, con un Ollama finto


def _ollama_finto(risposte, viste):
    """Un Ollama che risponde con `risposte` in ordine e ricorda cosa gli e' arrivato."""
    coda = list(risposte)

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        corpo = json.loads(richiesta.content)
        viste.append(corpo)
        if not coda:
            return httpx.Response(
                200, json={"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 500}
            )
        risposta = coda.pop(0)
        if isinstance(risposta, int):
            return httpx.Response(risposta, text="errore finto")
        return httpx.Response(200, json=risposta)

    return httpx.MockTransport(gestore)


def _con_strumento(nome, args, prompt_token=700):
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": nome, "arguments": args}}],
        },
        "prompt_eval_count": prompt_token,
    }


async def _esegui(banco, mondo, voce, risposte, num_ctx=2048, sempre=False):
    viste: list = []
    async with httpx.AsyncClient(transport=_ollama_finto(risposte, viste)) as cliente:
        misura = await banco.esegui_voce(
            cliente,
            "http://ollama.finto",
            "qwen2.5:3b",
            voce,
            mondo,
            "PROMPT",
            TOOLS_SCHEMA,
            set(_parametri()),
            num_ctx,
            0.4,
            ("accend", "spegn", "luce"),
            sempre,
        )
    return misura, viste


def test_gli_strumenti_vanno_al_modello_solo_se_la_frase_li_chiama(banco, mondo):
    saluto = {"id": "s", "categoria": "conversazione", "frase": "ciao come stai", "attesi": []}
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce della cucina", "attesi": []}

    _, viste_saluto = asyncio.run(_esegui(banco, mondo, saluto, []))
    _, viste_luce = asyncio.run(_esegui(banco, mondo, luce, []))

    assert "tools" not in viste_saluto[0], "una chiacchierata non deve ricevere il catalogo intero"
    assert len(viste_luce[0]["tools"]) == len(TOOLS_SCHEMA)


def test_dopo_uno_strumento_il_modello_rilegge_senza_strumenti(banco, mondo):
    """Come l'agente: gli strumenti si passano solo al primo giro. E' per questo che
    una richiesta a piu' passaggi riesce solo se le chiamate stanno nella stessa risposta."""
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce della cucina", "attesi": []}
    risposte = [_con_strumento("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]

    misura, viste = asyncio.run(_esegui(banco, mondo, luce, risposte))

    assert misura["giri"] == 2 and misura["chiamate"][0]["nome"] == "control_device"
    assert "tools" in viste[0] and "tools" not in viste[1]
    assert (
        viste[1]["messages"][-1]["role"] == "tool"
    ), "il risultato dello strumento non e' tornato al modello"


def test_con_strumenti_sempre_si_passano_a_ogni_giro(banco, mondo):
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce della cucina", "attesi": []}
    risposte = [_con_strumento("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]

    _, viste = asyncio.run(_esegui(banco, mondo, luce, risposte, sempre=True))

    assert "tools" in viste[0] and "tools" in viste[1]


def test_un_contesto_pieno_si_segnala_come_troncato(banco, mondo):
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce", "attesi": []}
    pieno = {"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 1024}
    intero = len(json.dumps(TOOLS_SCHEMA, ensure_ascii=False)) // 4  # quanto pesano gli strumenti da soli

    misura, _ = asyncio.run(_esegui(banco, mondo, luce, [pieno], num_ctx=1024))
    largo, _ = asyncio.run(
        _esegui(banco, mondo, luce, [{**pieno, "prompt_eval_count": intero + 50}], num_ctx=8192)
    )

    assert misura["troncato"] is True and misura["prompt_token"] == 1024
    assert largo["troncato"] is False


def test_un_prompt_letto_per_meta_e_troncato_anche_se_lontano_dal_limite(banco, mondo):
    """Il difetto del primo giro: con `num_ctx` 1024 il prompt da ~5.460 token risultava di 514, ben sotto
    il limite — e il vecchio controllo (`>= num_ctx - 8`) diceva «0 troncati su 114»."""
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce", "attesi": []}
    tagliato = {"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 514}

    misura, _ = asyncio.run(_esegui(banco, mondo, luce, [tagliato], num_ctx=1024))

    assert misura["troncato"] is True
    assert misura["prompt_atteso"] > 3000


def test_una_chiacchierata_senza_strumenti_non_e_troncata_se_e_corta(banco, mondo):
    ciao = {"id": "c", "categoria": "conversazione", "frase": "ciao come stai", "attesi": []}
    corto = {"message": {"role": "assistant", "content": "bene"}, "prompt_eval_count": 12}

    misura, _ = asyncio.run(_esegui(banco, mondo, ciao, [corto], num_ctx=1024))

    assert misura["troncato"] is False


def test_un_modello_che_chiama_strumenti_senza_fine_e_un_ciclo(banco, mondo):
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce della cucina", "attesi": []}
    sempre = [_con_strumento("get_home_status", {}) for _ in range(10)]

    misura, _ = asyncio.run(_esegui(banco, mondo, luce, sempre, sempre=True))

    assert misura["ciclo"] is True and misura["giri"] == banco.MAX_GIRI


def test_un_errore_di_ollama_si_registra_e_non_ferma_il_banco(banco, mondo):
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce della cucina", "attesi": []}

    misura, _ = asyncio.run(_esegui(banco, mondo, luce, [500]))

    assert "500" in misura["errore"] and misura["chiamate"] == []


def test_uno_strumento_scritto_come_testo_si_riconosce_come_fa_l_agente(banco, mondo):
    luce = {"id": "l", "categoria": "casa", "frase": "accendi la luce della cucina", "attesi": []}
    testuale = {
        "message": {
            "role": "assistant",
            "content": '[TOOL: control_device {"entity_id": "light.cucina", "action": "turn_on"}]',
        },
        "prompt_eval_count": 600,
    }

    misura, _ = asyncio.run(_esegui(banco, mondo, luce, [testuale]))

    assert misura["chiamate"][0] == {
        "nome": "control_device",
        "args": {"entity_id": "light.cucina", "action": "turn_on"},
    }


# ------------------------------------------------------------- il report


def _risultato(banco, mondo, voce, chiamate, secondi=2.0, **extra):
    esito = banco.valuta(voce, [banco.Chiamata(n, a) for n, a in chiamate], mondo.entita, set(_parametri()))
    base = {
        "voce": voce,
        "giri": 1,
        "prompt_token": 4800,
        "troncato": False,
        "errore": "",
        "ciclo": False,
        "secondi": secondi,
        "chiamate": [{"nome": n, "args": a} for n, a in chiamate],
    }
    return {**base, **esito, **extra}


def test_il_riassunto_conta_giusto_e_distingue_i_criteri(banco, mondo):
    bene = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]
    male = [("control_device", {"entity_id": "light.cantina", "action": "turn_on"})]
    risultati = [_risultato(banco, mondo, LUCE, bene, secondi=s) for s in (2, 3, 4, 5)] + [
        _risultato(banco, mondo, LUCE, male, secondi=6)
    ]

    riassunto = banco.riassumi(risultati)

    assert riassunto["richieste"] == 5 and riassunto["inventate"] == 1
    assert riassunto["argomenti_giusti"] == 80.0
    assert riassunto["mediana_secondi"] == 4

    # Una invenzione e' ancora dentro la soglia proposta (<= 1); due no.
    assert banco.regge(riassunto) is True
    due = [*risultati, _risultato(banco, mondo, LUCE, male, secondi=6)]
    assert banco.regge(banco.riassumi(due)) is False


def test_un_modello_senza_difetti_e_veloce_regge(banco, mondo):
    bene = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]
    risultati = [_risultato(banco, mondo, LUCE, bene, secondi=3) for _ in range(10)]

    assert banco.regge(banco.riassumi(risultati)) is True


def test_il_report_ha_la_tabella_la_macchina_e_dove_sbaglia(banco, mondo):
    male = [("get_home_status", {})]
    risultati = [_risultato(banco, mondo, {**LUCE, "id": "luce", "frase": "accendi la luce"}, male)]

    testo = banco.markdown({"qwen2.5:3b @ 1024": risultati}, "i5-8500T, 16 GB", 2)

    assert "i5-8500T, 16 GB" in testo
    assert "| qwen2.5:3b @ 1024 |" in testo
    assert "Dove sbaglia: qwen2.5:3b @ 1024" in testo and "accendi la luce" in testo
    assert "proposta" in testo, "i criteri vanno detti come una proposta, non come una verita'"


def test_prova_dice_che_il_prompt_non_ci_sta_nel_contesto_di_produzione(banco, capsys):
    import argparse

    args = argparse.Namespace(prova=True, solo=None, limite=None)
    assert asyncio.run(banco.principale(args)) == 0

    uscita = capsys.readouterr().out
    assert "num_ctx` di produzione" in uscita
    assert "Il prompt non ci sta" in uscita, "con 1024 token il prompt e gli schemi non possono starci"


# ----------------------------------------------- coerenza fra corpus e punteggio


def _chiamate_perfette(voce):
    """Quello che direbbe un modello perfetto: esattamente le chiamate attese."""

    def concreto(valore):
        if isinstance(valore, dict):
            if "una_di" in valore:
                return valore["una_di"][0]
            if "contiene" in valore:
                return f"x {valore['contiene']} y"
            return "qualcosa"
        return valore

    return [
        (a["tool"], {k: concreto(v) for k, v in (a.get("args") or {}).items()})
        for a in voce.get("attesi") or []
    ]


def test_un_modello_perfetto_prende_il_massimo_su_tutto_il_corpus(banco, mondo, voci):
    """Se il corpus attendesse una cosa che il punteggio non sa riconoscere, nessun
    modello, nemmeno uno perfetto, potrebbe prendere il massimo: il banco darebbe
    numeri bassi per colpa sua e non del modello."""
    sbagliate = []
    for voce in voci:
        esito = _valuta(banco, mondo, voce, _chiamate_perfette(voce))
        if not esito["ok_strumento"] or esito["ok_argomenti"] is False or esito["inventate"]:
            sbagliate.append(voce["id"])

    assert sbagliate == [], f"richieste in cui nemmeno un modello perfetto passa: {sbagliate}"


def test_un_modello_che_non_chiama_mai_niente_prende_solo_le_richieste_senza_strumento(banco, mondo, voci):
    """L'opposto: un modello muto non deve poter prendere un buon punteggio."""
    passate = [v for v in voci if _valuta(banco, mondo, v, [])["ok_strumento"]]

    assert all(not v.get("attesi") for v in passate)
    assert len(passate) < len(voci) / 3, "un modello che non fa niente prenderebbe troppo"


def test_il_report_parziale_si_scrive_e_poi_si_sovrascrive(banco, mondo, tmp_path, monkeypatch):
    import argparse

    monkeypatch.setattr(banco, "BANCO", tmp_path)
    args = argparse.Namespace(macchina="prova", ripetizioni=1, etichetta="giro")
    bene = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]

    banco.scrivi({"a @ 1024": [_risultato(banco, mondo, LUCE, bene)]}, args, parziale=True)
    primo = next((tmp_path / "risultati").glob("*-giro.md")).read_text(encoding="utf-8")
    banco.scrivi(
        {
            "a @ 1024": [_risultato(banco, mondo, LUCE, bene)],
            "b @ 1024": [_risultato(banco, mondo, LUCE, bene)],
        },
        args,
    )
    secondo = next((tmp_path / "risultati").glob("*-giro.md")).read_text(encoding="utf-8")

    assert "a @ 1024" in primo and "b @ 1024" not in primo
    assert "b @ 1024" in secondo
    assert json.loads(
        next((tmp_path / "risultati").glob("*-giro.json")).read_text(encoding="utf-8")
    ).keys() == {
        "a @ 1024",
        "b @ 1024",
    }


# ------------------------- cosa il primo giro sull'i5-8500T ha insegnato al banco (vedi l'analisi in risultati/)


def test_un_alias_valido_non_e_un_dispositivo_inventato(banco, mondo):
    """Gli strumenti risolvono «tapparella camera» come `cover.camera`: contarlo come invenzione era un falso."""
    voce = {"id": "t", "categoria": "tapparelle", "attesi": []}
    chiamate = [banco.Chiamata("comanda_tapparella", {"entity_id": "Tapparella Camera", "azione": "apri"})]

    esito = banco.valuta(voce, chiamate, mondo.entita | mondo.nomi, set(_parametri()))
    vero = banco.valuta(
        voce,
        [banco.Chiamata("control_device", {"entity_id": "light.cantina", "action": "turn_on"})],
        mondo.entita | mondo.nomi,
        set(_parametri()),
    )

    assert esito["inventate"] == []
    assert vero["inventate"] == ["light.cantina"], "un identificativo che non esiste resta un'invenzione"


def test_un_alias_negli_argomenti_vale_l_identificativo_che_risolve(banco, mondo):
    """Il secondo giro segnava 0/8 sulle tapparelle: il modello scriveva «tapparella salotto» e il banco
    voleva `cover.salotto`, che l'app invece ricava da sola. Era un falso negativo del banco, non del modello.
    """
    voce = {
        "id": "t",
        "categoria": "tapparelle",
        "attesi": [
            {"tool": "comanda_tapparella", "args": {"entity_id": "cover.salotto", "azione": "chiudi"}}
        ],
    }
    giusta = [banco.Chiamata("comanda_tapparella", {"entity_id": "Tapparella Salotto", "azione": "chiudi"})]
    altra = [banco.Chiamata("comanda_tapparella", {"entity_id": "tapparella camera", "azione": "chiudi"})]
    strumenti = set(_parametri())

    assert (
        banco.valuta(voce, giusta, mondo.entita | mondo.nomi, strumenti, mondo.alias)["ok_argomenti"] is True
    )
    assert (
        banco.valuta(voce, altra, mondo.entita | mondo.nomi, strumenti, mondo.alias)["ok_argomenti"] is False
    ), "un alias di un'altra stanza resta un errore"


def test_i_nomi_degli_alias_vengono_dal_mondo(mondo):
    assert "tapparella camera" in mondo.nomi and "luce cucina" in mondo.nomi


def _senza_risposta(banco, mondo, tipo):
    return _risultato(banco, mondo, LUCE, [], errore=f"{tipo}: ")


def test_un_timeout_non_e_uno_strumento_sbagliato(banco, mondo):
    bene = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]
    risultati = [_risultato(banco, mondo, LUCE, bene) for _ in range(9)] + [
        _senza_risposta(banco, mondo, "ReadTimeout")
    ]

    riassunto = banco.riassumi(risultati)

    assert riassunto["risposte"] == 9 and riassunto["richieste"] == 10
    assert riassunto["strumento_giusto"] == 100.0, "le percentuali sono sulle risposte arrivate"
    assert riassunto["tipi_errore"] == {"ReadTimeout": 1}
    assert riassunto["valutabile"] is True


def test_con_troppe_risposte_mancanti_la_riga_non_e_valutabile(banco, mondo):
    bene = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]
    risultati = [_risultato(banco, mondo, LUCE, bene) for _ in range(3)] + [
        _senza_risposta(banco, mondo, "ConnectError") for _ in range(7)
    ]

    riassunto = banco.riassumi(risultati)
    testo = banco.markdown({"qwen2.5:7b @ 1024": risultati}, "i5", 1)

    assert riassunto["valutabile"] is False and banco.regge(riassunto) is False
    assert "| qwen2.5:7b @ 1024 | 3/10 |" in testo and "n.v." in testo
    assert "Senza risposta" in testo and "7 ConnectError" in testo


def test_una_configurazione_mai_provata_non_scrive_percentuali(banco, mondo):
    risultati = [_senza_risposta(banco, mondo, "ConnectError") for _ in range(4)]

    testo = banco.markdown({"qwen2.5:7b @ 8192": risultati}, "i5", 1)

    assert "| qwen2.5:7b @ 8192 | 0/4 | — |" in testo and "n.v." in testo
    assert "0.0%" not in testo and "15.8%" not in testo


def test_il_report_riporta_lo_stato_della_macchina(banco, mondo):
    bene = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})]

    testo = banco.markdown(
        {"a @ 1024": [_risultato(banco, mondo, LUCE, bene)]},
        "i5",
        1,
        {"Ollama: CPU concessa (secondi di CPU al secondo)": "3s", "Ollama: priorita' (Nice)": "10"},
    )

    assert "Stato della macchina e limiti del servizio" in testo
    assert "CPU concessa" in testo and "(Nice)" in testo


def test_lo_stato_della_macchina_non_solleva_mai(banco, monkeypatch):
    def guasto(*a, **k):
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(banco.subprocess, "run", guasto)

    stato = banco.stato_macchina()

    assert stato["Core logici"].isdigit()


def _rete(gestore):
    return httpx.MockTransport(gestore)


def _corpo_ok(prompt_token=900):
    return httpx.Response(
        200, json={"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": prompt_token}
    )


def test_ollama_che_si_riavvia_in_mezzo_si_aspetta_e_la_richiesta_riprova(banco, mondo, monkeypatch):
    """Nel primo giro 244 richieste sono state scartate in 4 secondi mentre Ollama si riavviava."""
    monkeypatch.setattr(banco.TEMPI, "sonda", 0.0)
    monkeypatch.setattr(banco.TEMPI, "attesa_riavvio", 5.0)
    stato = {"chat": 0, "sonde": 0}

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        if richiesta.url.path == "/api/tags":
            stato["sonde"] += 1
            if stato["sonde"] < 3:
                raise httpx.ConnectError("riavvio")
            return httpx.Response(200, json={"models": []})
        stato["chat"] += 1
        if stato["chat"] == 1:
            raise httpx.ConnectError("ucciso dal kernel")
        return _corpo_ok()

    ciao = {"id": "c", "categoria": "conversazione", "frase": "ciao", "attesi": []}

    async def prova():
        async with httpx.AsyncClient(transport=_rete(gestore)) as cliente:
            return await banco.esegui_voce(
                cliente,
                "http://ollama.finto",
                "m",
                ciao,
                mondo,
                "P",
                TOOLS_SCHEMA,
                set(_parametri()),
                2048,
                0.4,
                ("luce",),
                False,
            )

    misura = asyncio.run(prova())

    assert misura["errore"] == "" and stato["chat"] == 2 and stato["sonde"] == 3


def test_ollama_che_non_torna_e_un_errore_non_un_giro_di_scarti_silenziosi(banco, mondo, monkeypatch):
    monkeypatch.setattr(banco.TEMPI, "sonda", 0.0)
    monkeypatch.setattr(banco.TEMPI, "attesa_riavvio", 0.05)

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("giu'")

    ciao = {"id": "c", "categoria": "conversazione", "frase": "ciao", "attesi": []}

    async def prova():
        async with httpx.AsyncClient(transport=_rete(gestore)) as cliente:
            return await banco.esegui_voce(
                cliente,
                "http://ollama.finto",
                "m",
                ciao,
                mondo,
                "P",
                TOOLS_SCHEMA,
                set(_parametri()),
                2048,
                0.4,
                ("luce",),
                False,
            )

    misura = asyncio.run(prova())

    assert misura["errore"].startswith("ConnectError")


def test_dopo_un_timeout_il_banco_aspetta_che_ollama_finisca(banco, mondo, monkeypatch):
    """Rinunciare non ferma Ollama: continua 40-70 secondi, e la richiesta dopo aspetta in coda (e scade)."""
    monkeypatch.setattr(banco.TEMPI, "dopo_timeout", 7.0)
    attese: list[float] = []

    async def finta_sleep(secondi):
        attese.append(secondi)

    monkeypatch.setattr(banco.asyncio, "sleep", finta_sleep)

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    ciao = {"id": "c", "categoria": "conversazione", "frase": "ciao", "attesi": []}

    async def prova():
        async with httpx.AsyncClient(transport=_rete(gestore)) as cliente:
            return await banco.esegui_voce(
                cliente,
                "http://ollama.finto",
                "m",
                ciao,
                mondo,
                "P",
                TOOLS_SCHEMA,
                set(_parametri()),
                2048,
                0.4,
                ("luce",),
                False,
            )

    misura = asyncio.run(prova())

    assert misura["errore"].startswith("ReadTimeout") and attese == [7.0]
    assert misura["secondi"] < 5, "la pausa non entra nel tempo della richiesta"


def test_il_riscaldamento_carica_il_modello_con_il_contesto_della_prova(banco):
    viste: list = []

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        viste.append(json.loads(richiesta.content))
        return _corpo_ok()

    async def prova():
        async with httpx.AsyncClient(transport=_rete(gestore)) as cliente:
            return await banco.scalda(cliente, "http://ollama.finto", "qwen2.5:3b", 8192)

    assert asyncio.run(prova()) == ""
    assert viste[0]["options"]["num_ctx"] == 8192 and viste[0]["options"]["num_predict"] == 1
    assert "tools" not in viste[0]


def _args_giro(tmp_path, **extra):
    import argparse

    base = {
        "modelli": ["m"],
        "num_ctx": ["1024"],
        "ripetizioni": 1,
        "temperatura": 0.4,
        "solo": "conversazione",
        "limite": 3,
        "url": "http://ollama.finto",
        "macchina": "prova",
        "etichetta": "giro",
        "strumenti_sempre": False,
        "prova": False,
        "timeout": 5.0,
        "dopo_timeout": 0.0,
        "attesa_riavvio": 0.05,
    }
    return argparse.Namespace(**{**base, **extra})


def _banco_in(tmp_path, banco, monkeypatch, gestore):
    import shutil

    shutil.copy(CORPUS, tmp_path / "corpus.yaml")
    monkeypatch.setattr(banco, "BANCO", tmp_path)
    monkeypatch.setattr(banco.TEMPI, "sonda", 0.0)
    originale = httpx.AsyncClient
    monkeypatch.setattr(banco.httpx, "AsyncClient", lambda *a, **k: originale(transport=_rete(gestore)))


def test_un_giro_intero_scalda_misura_e_scrive_lo_stato_della_macchina(banco, tmp_path, monkeypatch, capsys):
    viste: list = []

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        if richiesta.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        viste.append(json.loads(richiesta.content))
        return _corpo_ok(prompt_token=800)

    _banco_in(tmp_path, banco, monkeypatch, gestore)

    esito = asyncio.run(banco.principale(_args_giro(tmp_path)))

    assert esito == 0
    assert viste[0]["options"]["num_predict"] == 1, "la prima richiesta e' il riscaldamento"
    report = next((tmp_path / "risultati").glob("*-giro.md")).read_text(encoding="utf-8")
    assert "Stato della macchina e limiti del servizio" in report and "Core logici" in report
    assert "modello caricato" in capsys.readouterr().out


def test_se_ollama_non_risponde_il_giro_non_parte_e_non_scrive_niente(banco, tmp_path, monkeypatch):
    def gestore(richiesta: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("spento")

    _banco_in(tmp_path, banco, monkeypatch, gestore)
    monkeypatch.setattr(banco, "aspetta_ollama", lambda *a, **k: _falso())

    assert asyncio.run(banco.principale(_args_giro(tmp_path))) == 2
    assert not (tmp_path / "risultati").exists()


async def _falso():
    return False


def test_se_ollama_cade_a_meta_il_giro_si_ferma_e_salva_quello_che_ha(banco, tmp_path, monkeypatch):
    stato = {"richieste": 0}

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        if richiesta.url.path == "/api/tags":
            if stato["richieste"] >= 2:
                raise httpx.ConnectError("caduto")
            return httpx.Response(200, json={"models": []})
        stato["richieste"] += 1
        if stato["richieste"] > 2:
            raise httpx.ConnectError("caduto")
        return _corpo_ok(prompt_token=800)

    _banco_in(tmp_path, banco, monkeypatch, gestore)

    esito = asyncio.run(banco.principale(_args_giro(tmp_path, solo=None, limite=8)))

    assert esito == 2
    dati = json.loads(next((tmp_path / "risultati").glob("*-giro.json")).read_text(encoding="utf-8"))
    righe = dati["m @ 1024"]
    assert 3 <= len(righe) <= 6, "si ferma dopo tre guasti di fila, non consuma tutto il corpus"
    assert any(r["errore"] for r in righe)


# ------------------------------ gli strumenti arrivano al modello (il difetto che il banco ha trovato)


def test_ogni_richiesta_che_ha_uno_strumento_riceve_gli_strumenti(voci):
    """L'agente passa gli strumenti al modello solo se la frase contiene una delle
    `parole_azione` della lingua. Il banco, con un modello perfetto, ha mostrato che
    ventiquattro richieste su quarantotto non ne contenevano nessuna: liste, agenda,
    scadenze, energia, «metti il clima a 22», «porta la tapparella al 40»... Il
    modello le riceveva senza strumenti e non poteva che inventare la risposta. Lo
    stesso vale per qualunque richiesta nuova che si aggiunga al corpus."""
    from shinra.services.intenti.lingue import schemi

    parole = schemi("it").parole_azione
    senza = [v["frase"] for v in voci if v.get("attesi") and not any(k in v["frase"].lower() for k in parole)]

    assert senza == [], f"richieste con uno strumento atteso che non riceverebbero gli strumenti: {senza}"


def test_le_chiacchierate_non_ricevono_il_catalogo_intero(voci):
    """Il catalogo pesa ~4000 token: darlo a «ciao come stai» rallenta ogni risposta
    per niente, su una macchina che gia' fatica."""
    from shinra.services.intenti.lingue import schemi

    parole = schemi("it").parole_azione
    ricevono = [
        v["frase"]
        for v in voci
        if v["categoria"] in ("conversazione", "sicurezza_del_modello")
        and not v.get("attesi")
        and any(k in v["frase"].lower() for k in parole)
    ]

    assert ricevono == [], f"chiacchierate che riceverebbero tutti gli strumenti: {ricevono}"


def test_l_inglese_ha_le_stesse_famiglie_di_parole(voci):
    """Il file della lingua inglese deve coprire almeno gli stessi domini."""
    from shinra.services.intenti.lingue import schemi

    italiano, inglese = schemi("it").parole_azione, schemi("en").parole_azione

    assert len(inglese) >= len(italiano) * 0.6, f"parole_azione: it {len(italiano)}, en {len(inglese)}"
    for dominio in ("weather", "list", "reminder", "energy", "blind", "alarm", "vacuum"):
        assert any(dominio in p for p in inglese), f"nessuna parola inglese per «{dominio}»"


# ------------------------------------------------------------------ la modalita' agenti


def test_con_gli_agenti_il_modello_vede_solo_gli_strumenti_del_dominio(banco, mondo):
    voce = {"id": "t", "categoria": "tapparelle", "frase": "chiudi la tapparella del salotto", "attesi": []}

    async def una(agenti):
        viste: list = []
        async with httpx.AsyncClient(transport=_ollama_finto([], viste)) as cliente:
            misura = await banco.esegui_voce(
                cliente,
                "http://ollama.finto",
                "qwen2.5:3b",
                voce,
                mondo,
                "PROMPT",
                TOOLS_SCHEMA,
                set(_parametri()),
                2048,
                0.4,
                ("chiudi",),
                False,
                agenti,
            )
        return misura, viste

    intero, viste_intero = asyncio.run(una(False))
    agenti, viste_agenti = asyncio.run(una(True))

    assert len(viste_intero[0]["tools"]) == len(TOOLS_SCHEMA) and "agenti" not in intero
    nomi = {s["function"]["name"] for s in viste_agenti[0]["tools"]}
    assert nomi == {"comanda_clima", "stato_clima", "comanda_tapparella", "stato_tapparella"}
    assert agenti["agenti"] == ["clima_e_tapparelle"]


def test_con_gli_agenti_una_frase_che_il_router_non_riconosce_non_vede_strumenti(banco, mondo):
    voce = {"id": "t", "categoria": "casa", "frase": "metti qualcosa di bello", "attesi": []}

    async def una():
        viste: list = []
        async with httpx.AsyncClient(transport=_ollama_finto([], viste)) as cliente:
            misura = await banco.esegui_voce(
                cliente,
                "http://ollama.finto",
                "qwen2.5:3b",
                voce,
                mondo,
                "PROMPT",
                TOOLS_SCHEMA,
                set(_parametri()),
                2048,
                0.4,
                ("metti",),
                False,
                True,
            )
        return misura, viste

    misura, viste = asyncio.run(una())

    assert "tools" not in viste[0] and misura["agenti"] == []
