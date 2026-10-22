"""Il banco dei piani misura quello che dice di misurare (#430).

Gira in CI senza rete e senza modello: il corpus e' valido (ogni strumento e ogni dispositivo esiste), la lettura e la validazione di un
piano sono giuste (anche con un modello che scrive male o inventa), il verdetto e' quello del banco del tool calling, e il report si scrive.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def banco():
    sys.path.insert(0, str(RADICE / "scripts"))
    spec = importlib.util.spec_from_file_location("banco_piani", RADICE / "scripts" / "banco_piani.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def mondo(banco):
    return banco.bt.Mondo.carica()


@pytest.fixture(scope="module")
def strumenti():
    from shinra.skills.registry import TOOLS_SCHEMA

    return {s["function"]["name"] for s in TOOLS_SCHEMA}


# ------------------------------------------------------------------ il corpus


def test_il_corpus_e_valido(banco, mondo, strumenti):
    corpus = banco.carica_corpus()
    ids = [v["id"] for v in corpus]
    assert len(ids) == len(set(ids)), "richieste con lo stesso id"
    categorie = {v["categoria"] for v in corpus}
    assert {
        "due_passi",
        "tre_passi",
        "quattro_e_piu",
        "con_dipendenza",
        "ambigua",
        "sconosciuta",
    } <= categorie
    for v in corpus:
        for attesa in v.get("attesi") or []:
            assert attesa["tool"] in strumenti, f"{v['id']}: lo strumento {attesa['tool']} non esiste"
            dispositivo = (attesa.get("args") or {}).get("entity_id")
            if isinstance(dispositivo, str):
                assert (
                    dispositivo in mondo.entita
                ), f"{v['id']}: il dispositivo {dispositivo} non e' nella casa finta"
    for v in corpus:
        if v["categoria"] in ("due_passi", "tre_passi", "quattro_e_piu"):
            minimo = {"due_passi": 2, "tre_passi": 3, "quattro_e_piu": 4}[v["categoria"]]
            assert len(v["attesi"]) >= minimo, f"{v['id']}: meno passi di quelli della sua categoria"
        if v["categoria"] in ("ambigua", "sconosciuta"):
            assert not v["attesi"], f"{v['id']}: una richiesta da fermare non ha uno strumento giusto"


# ------------------------------------------------------------------ leggere il piano


@pytest.mark.parametrize(
    "testo",
    [
        '{"passi": [{"strumento": "control_device", "argomenti": {"entity_id": "light.cucina", "action": "turn_on"}}], "chiedi": null}',
        '```json\n{"passi": [{"strumento": "control_device", "argomenti": {}}]}\n```',
        'Ecco il piano: {"passi": [{"strumento": "stato_aperture"}], "chiedi": null} spero vada bene',
        '{"x": 1} {"passi": []}',
    ],
)
def test_un_piano_si_legge_anche_se_il_modello_ci_scrive_attorno(banco, testo):
    assert isinstance(banco.leggi_piano(testo)["passi"], list)


@pytest.mark.parametrize(
    "testo", ["", "nessun piano", "{non json}", '{"passi": "uno"}', '{"altro": []}', "[1, 2]"]
)
def test_un_piano_illeggibile_e_none(banco, testo):
    assert banco.leggi_piano(testo) is None


# ------------------------------------------------------------------ validare il piano


def piano(*passi):
    return {"passi": [{"strumento": n, "argomenti": a} for n, a in passi]}


def test_un_piano_giusto_passa_intero(banco, mondo, strumenti):
    accettati, scarti = banco.valida_piano(
        piano(
            ("control_device", {"entity_id": "light.cucina", "action": "turn_off"}),
            (
                "comanda_tapparella",
                {"entity_id": "tapparella salotto", "azione": "chiudi"},
            ),  # un alias e' valido
        ),
        strumenti,
        mondo,
    )
    assert [c.nome for c in accettati] == ["control_device", "comanda_tapparella"] and scarti == []


def test_il_modello_non_e_fidato_strumenti_e_dispositivi_inventati_si_scartano(banco, mondo, strumenti):
    accettati, scarti = banco.valida_piano(
        piano(
            ("apri_il_garage", {"entity_id": "cover.garage"}),
            ("control_device", {"entity_id": "light.mansarda", "action": "turn_on"}),
            ("control_device", {"entity_id": "light.cucina", "action": "turn_on"}),
        ),
        strumenti,
        mondo,
    )
    assert [c.args["entity_id"] for c in accettati] == ["light.cucina"]
    assert len(scarti) == 2 and "non esiste" in scarti[0] and "non c'e' in casa" in scarti[1]


def test_passi_che_non_sono_oggetti_si_scartano_senza_rompere_niente(banco, mondo, strumenti):
    accettati, scarti = banco.valida_piano(
        {
            "passi": [
                "accendi",
                7,
                {"strumento": "stato_aperture", "argomenti": "tutte"},
                {"strumento": "stato_aperture"},
            ]
        },
        strumenti,
        mondo,
    )
    assert [c.nome for c in accettati] == ["stato_aperture"] and len(scarti) == 3


def test_un_modello_che_continua_ad_aggiungere_passi_si_ferma_al_tetto(banco, mondo, strumenti):
    passi = [("control_device", {"entity_id": "light.cucina", "action": "turn_on"})] * 30
    accettati, scarti = banco.valida_piano(piano(*passi), strumenti, mondo)
    assert len(accettati) == banco.MAX_PASSI
    assert any("tetto" in s for s in scarti)


def test_il_catalogo_compatto_e_corto_e_segna_gli_obbligatori(banco):
    from shinra.skills.registry import TOOLS_SCHEMA

    catalogo = banco.catalogo_compatto(TOOLS_SCHEMA)
    assert "- control_device(entity_id*, action*" in catalogo
    assert (
        len(catalogo) // 4 < 1500
    ), "il catalogo compatto deve costare poche centinaia di token, non migliaia"


# ------------------------------------------------------------------ il verdetto


def esito(*chiamate):
    return {"chiamate": [{"nome": n, "args": a} for n, a in chiamate], "secondi": 1.0}


def voce_di(banco, id_):
    return next(v for v in banco.carica_corpus() if v["id"] == id_)


def test_il_verdetto_e_quello_del_banco_del_tool_calling(banco, mondo, strumenti):
    v = voce_di(banco, "p-cucina-e-clima")
    giusto = esito(
        ("control_device", {"entity_id": "light.cucina", "action": "turn_off"}),
        ("comanda_clima", {"entity_id": "climate.camera", "azione": "temperatura", "temperatura": 20}),
    )
    assert banco.verdetto(v, giusto, mondo, strumenti)["riuscita"] is True
    una_sola = esito(("control_device", {"entity_id": "light.cucina", "action": "turn_off"}))
    assert banco.verdetto(v, una_sola, mondo, strumenti)["riuscita"] is False


def test_il_se_piove_vuole_leggere_e_non_chiudere(banco, mondo, strumenti):
    """Nella casa finta domani e' sereno: chiudere comunque la tapparella e' sbagliato, anche se «sembra» coerente."""
    v = voce_di(banco, "p-se-piove-no")
    assert banco.verdetto(v, esito(("get_weather", {"location": "Bologna"})), mondo, strumenti)["riuscita"]
    chiude = esito(
        ("get_weather", {"location": "Bologna"}),
        ("comanda_tapparella", {"entity_id": "cover.salotto", "azione": "chiudi"}),
    )
    assert not banco.verdetto(v, chiude, mondo, strumenti)["riuscita"]


def test_una_richiesta_da_fermare_passa_solo_se_non_comanda_niente(banco, mondo, strumenti):
    v = voce_di(banco, "p-ambigua-luci")
    assert banco.verdetto(v, esito(), mondo, strumenti)["riuscita"]
    assert not banco.verdetto(
        v, esito(("control_device", {"entity_id": "light.cucina", "action": "turn_on"})), mondo, strumenti
    )["riuscita"]


def test_un_dispositivo_inventato_o_un_errore_non_e_mai_una_riuscita(banco, mondo, strumenti):
    v = voce_di(banco, "p-tutte-le-luci")
    inventato = esito(
        *[
            ("control_device", {"entity_id": f"light.{n}", "action": "turn_off"})
            for n in ("cucina", "salotto", "camera", "mansarda")
        ]
    )
    assert not banco.verdetto(v, inventato, mondo, strumenti)["riuscita"]
    con_errore = {**esito(), "errore": "ReadTimeout: lento"}
    assert not banco.verdetto(voce_di(banco, "p-ambigua-luci"), con_errore, mondo, strumenti)["riuscita"]


# ------------------------------------------------------------------ il report


def test_il_report_conta_e_si_scrive(banco, mondo, strumenti):
    corpus = {v["id"]: v for v in banco.carica_corpus()}
    risultati = []
    perfetto = esito(
        ("control_device", {"entity_id": "light.cucina", "action": "turn_off"}),
        ("comanda_clima", {"entity_id": "climate.camera", "azione": "temperatura", "temperatura": 20}),
    )
    sbagliato = esito(("control_device", {"entity_id": "light.cucina", "action": "turn_off"}))
    for strategia, e in (("solo", sbagliato), ("piano", perfetto)):
        v = corpus["p-cucina-e-clima"]
        risultati.append(
            {
                "giro": 0,
                "strategia": strategia,
                "voce": v,
                "esito": e,
                "verdetto": banco.verdetto(v, e, mondo, strumenti),
            }
        )
    testo = banco.markdown(
        {
            "data": "2026-10-21",
            "modello": "finto",
            "macchina": "prova",
            "num_ctx": 4096,
            "richieste": 1,
            "ripetizioni": 1,
        },
        risultati,
    )
    assert "| due_passi | 0/1 (0%) | 1/1 (100%) |" in testo
    assert "Dove sbaglia" in testo and "`solo` · p-cucina-e-clima" in testo
    assert banco.riepilogo(risultati[:1])["riuscite"] == 0 and banco.riepilogo(risultati[1:])["riuscite"] == 1


# ------------------------------------------------------------------ «scomposto»: il codice spezza la frase


@pytest.fixture(scope="module")
def parole():
    from shinra.infra.lingue import schemi

    return schemi("it").parole_azione


@pytest.mark.parametrize(
    ("frase", "attesi"),
    [
        (
            "chiudi la tapparella del salotto e accendi la luce del salotto",
            ["chiudi la tapparella del salotto", "accendi la luce del salotto"],
        ),
        (
            "dimmi che tempo fa a Roma e ricordami di chiamare il dentista",
            ["dimmi che tempo fa a Roma", "ricordami di chiamare il dentista"],
        ),
        # un pezzo senza azione non e' un'azione: si riattacca al vicino
        (
            "accendi le luci del bagno e della camera e porta il clima del salotto a 22",
            ["accendi le luci del bagno e della camera", "porta il clima del salotto a 22"],
        ),
        (
            "vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme",
            ["vado a dormire spegni le luci di salotto e cucina", "attiva l'allarme"],
        ),
        # una sola cosa da fare: la frase intera
        ("accendi la luce della cucina", ["accendi la luce della cucina"]),
    ],
)
def test_il_codice_spezza_una_frase_in_una_cosa_per_pezzo(banco, parole, frase, attesi):
    assert banco.spezza(frase, parole) == attesi


def test_una_e_dentro_una_parola_o_con_l_apostrofo_non_taglia(banco, parole):
    assert len(banco.spezza("guarda com'e' il clima del salotto", parole)) == 1
    assert banco.spezza("spegni la tv e basta", parole)[0].startswith("spegni la tv")


@pytest.mark.parametrize("frase", ["", "ciao come stai", "e e e", ", ,"])
def test_senza_azioni_riconoscibili_non_si_inventa_niente(banco, parole, frase):
    assert banco.spezza(frase, parole) in ([frase], [])  # la frase com'e': mai pezzi inventati
    assert len(banco.spezza(frase, parole)) <= 1


def test_i_pezzi_hanno_un_tetto(banco, parole):
    frase = " e ".join(f"accendi la luce {n}" for n in range(30))
    assert len(banco.spezza(frase, parole)) == banco.MASSIMO_PEZZI


async def test_ogni_pezzo_passa_dal_ciclo_con_il_router_e_il_risultato_si_valida(
    banco, mondo, strumenti, monkeypatch
):
    """Un finto ciclo per pezzo: due pezzi, uno con un dispositivo inventato. I risultati si uniscono, i doppioni cadono, l'invenzione si scarta."""
    visti = []

    async def finto(
        cliente,
        url,
        modello,
        voce,
        mondo_,
        prompt,
        schemi_,
        strumenti_,
        num_ctx,
        temp,
        parole_,
        sempre,
        agenti=False,
        contesto="",
    ):
        visti.append((voce["frase"], agenti))
        if "tapparella" in voce["frase"]:
            return {
                "giri": 1,
                "chiamate": [
                    {"nome": "comanda_tapparella", "args": {"entity_id": "cover.salotto", "azione": "chiudi"}}
                ],
            }
        return {
            "giri": 1,
            "chiamate": [
                {"nome": "control_device", "args": {"entity_id": "light.salotto", "action": "turn_on"}},
                {
                    "nome": "control_device",
                    "args": {"entity_id": "light.salotto", "action": "turn_on"},
                },  # doppione
                {
                    "nome": "control_device",
                    "args": {"entity_id": "light.mansarda", "action": "turn_on"},
                },  # inventata
            ],
        }

    monkeypatch.setattr(banco.bt, "esegui_voce", finto)
    monkeypatch.setattr(banco.bt, "contesto_di_richiesta", lambda m: "")
    voce = {
        "id": "x",
        "categoria": "due_passi",
        "frase": "chiudi la tapparella del salotto e accendi la luce del salotto",
    }
    from shinra.infra.lingue import schemi
    from shinra.skills.registry import TOOLS_SCHEMA

    esito = await banco.esegui_scomposto(
        None, "u", "m", voce, mondo, "p", TOOLS_SCHEMA, strumenti, 4096, 0.1, schemi("it").parole_azione
    )
    assert [f for f, _ in visti] == ["chiudi la tapparella del salotto", "accendi la luce del salotto"]
    assert all(agenti for _, agenti in visti), "ogni pezzo passa dal router per dominio"
    assert [c["nome"] for c in esito["chiamate"]] == [
        "comanda_tapparella",
        "control_device",
    ], "un doppione e un'invenzione non entrano"
    assert len(esito["scarti"]) == 1 and "mansarda" in esito["scarti"][0]
    assert esito["pezzi"] == ["chiudi la tapparella del salotto", "accendi la luce del salotto"]


# ------------------------------------------------------------------ le due migliorie senza modello


def test_un_obbligatorio_ovvio_si_completa_e_uno_incerto_no(banco):
    from shinra.skills.registry import TOOLS_SCHEMA

    schemi = banco.schemi_per_nome(TOOLS_SCHEMA)
    # «metti il clima a 20 gradi»: c'e' `temperatura`, e `temperatura` e' una delle scelte di `azione`
    completato, mancanti = banco.completa_argomenti(
        {"entity_id": "climate.camera", "temperatura": 20}, schemi["comanda_clima"]
    )
    assert completato["azione"] == "temperatura" and mancanti == []
    # niente da cui dedurlo: non si indovina
    _, mancanti = banco.completa_argomenti({"entity_id": "climate.camera"}, schemi["comanda_clima"])
    assert mancanti == ["azione"]
    # due scelte possibili (due nomi di argomento che sono valori di `azione`): ambiguo, non si completa
    _, mancanti = banco.completa_argomenti(
        {"entity_id": "climate.camera", "temperatura": 20, "umidita": 40}, schemi["comanda_clima"]
    )
    assert mancanti == ["azione"]
    # un parametro gia' dato non si tocca
    completato, _ = banco.completa_argomenti(
        {"entity_id": "climate.camera", "azione": "spegni", "temperatura": 20}, schemi["comanda_clima"]
    )
    assert completato["azione"] == "spegni"


def test_un_passo_senza_i_suoi_obbligatori_si_scarta_dicendo_cosa_manca(banco, mondo, strumenti):
    from shinra.skills.registry import TOOLS_SCHEMA

    schemi = banco.schemi_per_nome(TOOLS_SCHEMA)
    accettati, scarti = banco.valida_piano(
        piano(
            ("comanda_clima", {"entity_id": "climate.camera"}),
            ("comanda_clima", {"entity_id": "climate.camera", "temperatura": 20}),
        ),
        strumenti,
        mondo,
        schemi=schemi,
    )
    assert [c.args.get("azione") for c in accettati] == ["temperatura"]
    assert len(scarti) == 1 and "azione" in scarti[0] and "obbligatorio" in scarti[0]


def test_senza_gli_schemi_la_validazione_e_quella_di_prima(banco, mondo, strumenti):
    accettati, scarti = banco.valida_piano(
        piano(("comanda_clima", {"entity_id": "climate.camera"})), strumenti, mondo
    )
    assert len(accettati) == 1 and scarti == []


def test_il_pronome_prende_il_nome_dell_ultimo_dispositivo_detto(banco, parole):
    pezzi = banco.spezza("spegni la luce del salotto e accendi quella del corridoio", parole)
    assert pezzi == ["spegni la luce del salotto", "accendi la luce del corridoio"]
    # senza un nome prima, il pronome resta com'e': non si inventa
    assert banco.spezza("accendi quella del corridoio", parole) == ["accendi quella del corridoio"]


def test_ventila_e_una_parola_d_azione_nell_esperimento(banco, parole):
    senza = banco.spezza("spegni la luce del salotto e ventila lo studio", parole)
    con = banco.spezza("spegni la luce del salotto e ventila lo studio", (*parole, *banco.PAROLE_IN_PIU))
    assert len(senza) == 1 and len(con) == 2
