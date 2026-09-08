"""Lo script che aggiorna il server, e le due cose che lo rendono inaffidabile.

`scripts/deploy.sh` sono quasi cinquecento righe di bash che aggiornano il
servizio in casa, e non le guardava niente. Ha gia' rotto due
aggiornamenti reali: una volta perche' `ls` con `pipefail` usciva 2 quando
il glob non trovava nulla, una volta perche' un secondo `trap ... EXIT`
sostituisce silenziosamente il primo.

Qui si controllano le due cose che si possono controllare senza un server:
che il file sia bash valido, e che `--dry-run` non menta.

Riferimento: issue #16.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent.parent
SCRIPT = RADICE / "scripts" / "deploy.sh"


def test_lo_script_e_bash_valido():
    """Un errore di sintassi qui si scopre a meta' di un aggiornamento.

    Il servizio e' gia' fermo, il codice a meta' strada, e la riga che
    doveva riavviarlo non viene mai letta: bash legge gli script man mano
    che li esegue.
    """
    if shutil.which("bash") is None:
        pytest.skip("bash non disponibile: in CI c'e'")

    esito = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert esito.returncode == 0, f"deploy.sh non compila:\n{esito.stderr}"


# I verbi di git che leggono e basta. `esegui` esiste per non fare le cose
# durante una simulazione: avvolgere una lettura significa non farla, e
# tutto cio' che viene dopo ragiona su dati vecchi.
SOLA_LETTURA = (
    "fetch",
    "rev-parse",
    "rev-list",
    "show-ref",
    "log",
    "ls-files",
    "diff",
    "status",
    "describe",
    "tag --list",
)


def test_la_simulazione_non_salta_le_letture():
    """`--dry-run` deve dire cosa succederebbe, non «niente».

    `esegui git_utente fetch` sembrava prudente e invece era il difetto: il
    fetch aggiorna solo i riferimenti remoti, non tocca la copia di lavoro.
    Saltarlo lasciava lo script a confrontare HEAD con se stesso, e la
    simulazione rispondeva «gia' aggiornato» mentre sul server mancavano
    tre versioni. Una prova che risponde sempre allo stesso modo non prova
    niente.
    """
    avvolte = []
    for numero, riga in enumerate(SCRIPT.read_text(encoding="utf-8").splitlines(), 1):
        spoglia = riga.strip()
        if not spoglia.startswith("esegui "):
            continue
        comando = spoglia.removeprefix("esegui ")
        if not re.match(r"^(git|git_utente)\b", comando):
            continue
        for verbo in SOLA_LETTURA:
            if re.search(rf"\b{re.escape(verbo)}\b", comando):
                avvolte.append(f"riga {numero}: {spoglia}")
                break

    assert avvolte == [], (
        "queste letture di git passano da `esegui`, quindi durante --dry-run "
        f"non vengono eseguite e tutto cio' che segue ragiona su dati vecchi: {avvolte}"
    )


def test_la_simulazione_esce_prima_della_verifica_di_salute():
    """La simulazione deve fermarsi prima del controllo di salute.

    Quel controllo interroga il servizio e, se non risponde, riporta da solo
    il server alla versione precedente: riavvia, reinstalla, rimette il
    codice vecchio. Durante una simulazione il servizio non e' stato
    riavviato, quindi il controllo guarderebbe il processo gia' in
    esecuzione — e se quello fosse gia' giu' per conto suo, un innocuo
    `--dry-run` scatenerebbe un ripristino vero.

    Tutto cio' che modifica prima di questo punto passa da `esegui` o sta
    dentro un ramo `DRY_RUN -eq 0`; da qui in poi non serve piu', perche'
    non ci si arriva.
    """
    righe = SCRIPT.read_text(encoding="utf-8").splitlines()

    uscita = next(
        (
            numero
            for numero, riga in enumerate(righe)
            if "DRY_RUN -eq 1" in riga and any("exit 0" in r for r in righe[numero : numero + 6])
        ),
        None,
    )
    assert uscita is not None, "la simulazione non esce mai: --dry-run modificherebbe il server"

    salute = next(
        (numero for numero, riga in enumerate(righe) if "TENTATIVI_HEALTH" in riga and "seq" in riga),
        None,
    )
    assert salute is not None, "il controllo di salute e' sparito: questo test non guarda piu' niente"

    assert uscita < salute, (
        f"la simulazione esce alla riga {uscita + 1}, dopo il controllo di salute "
        f"(riga {salute + 1}): un --dry-run potrebbe far partire un ripristino vero"
    )
