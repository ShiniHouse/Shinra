"""Le guide dicono cose vere e portano a file che esistono.

Una guida all'uso invecchia peggio del codice: nessuno la esegue. Un comando
che rimanda a uno script rinominato, un collegamento a un documento spostato,
un modello consigliato che non e' piu' quello configurato — nessuna di queste
tre cose rompe niente, e tutte e tre fanno perdere un pomeriggio a chi sta
installando Shinra per la prima volta.

Il sesto punto del collaudo della #38 era esattamente questo: «i parametri di
configurazione documentavano uno schema che non esiste». Quel difetto ha una
guardia in `test_coerenza_configurazione.py`; questo file guarda le altre due
forme, i collegamenti e i comandi.

Riferimento: issue #38.
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
GUIDE = [
    RADICE / "README.md",
    RADICE / "docs" / "PRIMI-PASSI.md",
    RADICE / "docs" / "PROBLEMI.md",
    RADICE / "docs" / "DEPLOY.md",
    RADICE / "docs" / "ARCHITECTURE.md",
    RADICE / "CONTRIBUTING.md",
    RADICE / "SECURITY.md",
]

# `[testo](percorso)` — solo i collegamenti a file nostri: niente http, niente
# ancore interne alla stessa pagina, niente mailto.
COLLEGAMENTO = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

# `scripts/imposta_pin.py` ovunque compaia, anche dentro un comando.
COPIONE = re.compile(r"\bscripts/([\w.-]+\.(?:py|sh))\b")


def _guide_esistenti() -> list[Path]:
    presenti = [g for g in GUIDE if g.is_file()]
    assert len(presenti) >= 6, f"guide trovate: {[g.name for g in presenti]}"
    return presenti


def test_ogni_collegamento_fra_i_documenti_porta_da_qualche_parte():
    """Un collegamento rotto in una guida e' un vicolo cieco per chi legge.

    Non solleva, non compare in nessun log: si scopre solo leggendo, e chi
    legge una guida di solito non conosce il progetto abbastanza da indovinare
    dove sia finito il documento.
    """
    rotti = []
    for guida in _guide_esistenti():
        for riferimento in COLLEGAMENTO.findall(guida.read_text(encoding="utf-8")):
            if riferimento.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            percorso = (guida.parent / riferimento.split("#", 1)[0]).resolve()
            if not percorso.exists():
                rotti.append(f"{guida.relative_to(RADICE)} -> {riferimento}")

    assert rotti == [], f"collegamenti che non portano da nessuna parte: {rotti}"


def test_ogni_copione_nominato_dalle_guide_esiste():
    """«Se e' scorso via, si reimposta con `scripts/imposta_pin.py`».

    Una riga cosi' vale finche' quel file si chiama cosi'. Rinominarlo e'
    un secondo; accorgersi che tre guide lo nominano ancora al vecchio nome
    non succede mai da solo.
    """
    mancanti = []
    trovati = 0
    for guida in _guide_esistenti():
        for nome in COPIONE.findall(guida.read_text(encoding="utf-8")):
            trovati += 1
            if not (RADICE / "scripts" / nome).is_file():
                mancanti.append(f"{guida.relative_to(RADICE)} nomina scripts/{nome}")

    assert trovati >= 3, f"nessuna guida nomina piu' uno script: trovati {trovati}"
    assert mancanti == [], f"script nominati dalle guide e inesistenti: {mancanti}"


def test_le_guide_nuove_sono_nell_indice_del_readme():
    """Una guida che il README non elenca la trova solo chi gia' sa che c'e'.

    E' la stessa forma del registro degli ADR, che aveva perso l'0005: scritto,
    salvato, mai entrato nell'indice.
    """
    indice = (RADICE / "README.md").read_text(encoding="utf-8")
    fuori = [
        g.name
        for g in _guide_esistenti()
        if g.name != "README.md" and f"docs/{g.name}" not in indice and g.name not in indice
    ]
    assert fuori == [], f"guide che il README non elenca: {fuori}"


def test_la_guida_ai_problemi_dice_quale_modello_serve():
    """Il guasto piu' caro di tutti, e quello che la guida esiste per chiudere.

    In casa e' girata per settimane con `llama3.2:1b` configurato: la casa
    rispondeva, le frasi avevano senso, e non succedeva niente. Se la guida
    nomina un modello diverso da quello che il codice configura per difetto,
    manda a cercare dalla parte sbagliata proprio chi ha gia' quel problema.
    """
    from shinra.config.settings import AppConfig

    predefinito = AppConfig().llm.model
    testo = (RADICE / "docs" / "PROBLEMI.md").read_text(encoding="utf-8")

    assert predefinito in testo, (
        f"la guida ai problemi non nomina `{predefinito}`, che e' il modello "
        "predefinito: chi ha il modello sbagliato non trova la riga che glielo dice"
    )

    # E non deve consigliarne un altro come se fosse quello giusto.
    famiglia = predefinito.split(":")[0].lower()
    for altra in ("gemma", "llama", "mistral", "phi", "qwen"):
        # `qwen` e' il prefisso di `qwen2.5`: confrontare i due nomi per
        # uguaglianza faceva accusare la riga giusta, quella che dice qual e'
        # il modello predefinito. Una guardia che grida al lupo su un
        # innocente viene disattivata alla seconda volta.
        if famiglia.startswith(altra):
            continue
        for riga in testo.splitlines():
            # Le righe che nominano un modello come **esempio di guasto** sono
            # legittime: e' il caso di `llama3.2:1b`, che sta li' proprio
            # perche' e' quello che ha causato il difetto.
            if "difetto" in riga or "guasto" in riga or "girata" in riga:
                continue
            assert not re.search(rf"\b{altra}[\d.:]*\b", riga, re.I), (
                f"la guida consiglia `{altra}` mentre il predefinito e' "
                f"`{predefinito}`: {riga.strip()[:90]}"
            )


def test_la_guida_ai_primi_passi_porta_a_quella_dei_problemi_e_viceversa():
    """Le due guide coprono i due momenti in cui si e' piu' soli: la prima
    configurazione e il primo guasto. Chi e' in uno dei due deve trovare
    l'altra senza cercarla."""
    primi = (RADICE / "docs" / "PRIMI-PASSI.md").read_text(encoding="utf-8")
    problemi = (RADICE / "docs" / "PROBLEMI.md").read_text(encoding="utf-8")

    assert "PROBLEMI.md" in primi, "dai primi passi non si arriva alla guida dei problemi"
    assert "PRIMI-PASSI.md" in problemi, "dalla guida dei problemi non si torna ai primi passi"
