"""La versione negli indirizzi dei moduli della dashboard (issue #34, ADR 0006).

I moduli ES si importano a vicenda con indirizzi senza versione:
`import { Stato } from './stato.js'`. Solo il punto d'ingresso, `principale.js`,
ha `?v=<versione>` nell'indirizzo, perche' lo scrive il template. Quindi dopo un
aggiornamento il browser prende subito l'ingresso nuovo e poi, per tutto il
resto, si fida della propria cache.

Il server risponde a `/static/` con `Cache-Control: no-cache`, e basterebbe —
se fra il server e il browser non ci fosse niente. Dietro Cloudflare (che la
maggior parte delle installazioni ha, per Alexa) quell'intestazione viene
riscritta in `max-age=14400`: quattro ore in cui il browser non chiede nulla,
e la dashboard gira con un pezzo di codice nuovo e uno vecchio. Si e' visto
cosi', guardando le intestazioni di un server vero.

L'import map risolve la cosa alla radice, senza dipendere da nessuno: dice al
browser che `/static/js/stato.js` si legge da `/static/js/stato.js?v=...`.
Cambia la versione, cambiano tutti gli indirizzi, e nessuna cache in mezzo
puo' servire il file di prima. Vale anche per gli `import()` dinamici.
"""

from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import quote

from shinra import percorsi

INGRESSO = "principale.js"


@lru_cache(maxsize=8)
def mappa_dei_moduli(descrizione: str) -> str:
    """Il contenuto JSON dell'import map, pronto da mettere in un `<script>`.

    L'ingresso resta fuori: ha gia' la sua versione nell'indirizzo, scritta dal
    template, e rimapparlo lo avrebbe fatto caricare due volte.
    """
    cartella = percorsi.STATICI / "js"
    versione = quote(descrizione or "dev", safe="")
    imports = {
        f"/static/js/{p.name}": f"/static/js/{p.name}?v={versione}"
        for p in sorted(cartella.glob("*.js"))
        if p.name != INGRESSO
    }
    testo = json.dumps({"imports": imports}, ensure_ascii=True, separators=(",", ":"))
    # Dentro un `<script>` una `</script>` chiude il blocco comunque sia scritta
    # nel JSON: la versione viene da `git describe`, ma un'abitudine sicura
    # costa una riga.
    return testo.replace("<", "\u003c").replace(">", "\u003e").replace("&", "\u0026")
