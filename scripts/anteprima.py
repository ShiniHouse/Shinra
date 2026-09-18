"""Prepara una copia statica della dashboard, da servire e da guidare.

Serve ai test dei gesti (`tests/gesti/`), che chiedono a un browser vero
se un pulsante si puo' premere davvero.

Perche' non l'applicazione vera: i gesti dell'editor a nodi, della barra
e delle finestre vivono tutti nel browser e non toccano il server.
Servirli da un file statico toglie di mezzo l'autenticazione, il
database e lo scheduler — cioe' tutto cio' che potrebbe far fallire un
test per ragioni che non c'entrano con il gesto in prova.

Cosa **non** si puo' provare cosi': tutto quello che passa da una
chiamata all'API, perche' qui risponde 404. Se un giorno servisse,
la strada e' far girare l'applicazione vera e dare al browser una
sessione; ma sarebbe un altro tipo di prova, piu' lenta e piu' fragile.

Il segnaposto delle espressioni Jinja non usa DOTALL e non accetta
graffe annidate: la prima versione, scritta con `.*?` e `re.S`,
mangiava cinquantaquattro caratteri di JavaScript vero fra la prima
`{{` e la `}}` piu' vicina, e la pagina si apriva con il copione morto.
"""

from __future__ import annotations

import re
import shutil
import sys

from shinra import percorsi

FUORI = percorsi.RADICE / ".anteprima"

# `{% ... %}` sparisce, `{{ ... }}` diventa una parola. Niente DOTALL, e
# niente graffe dentro l'espressione: cosi' il segnaposto non puo'
# scavalcare un `${...}` del JavaScript.
BLOCCHI = re.compile(r"\{%[^%]*%\}")
ESPRESSIONI = re.compile(r"\{\{[^{}]*\}\}")

# Solo per l'anteprima: `?scheda=automazioni` apre quella scheda,
# `&editor=1` apre l'editor a nodi, `&tema=light` fotografa di giorno.
# Serve a fotografare e a guidare schermate diverse dalla console. Non
# finisce in produzione: sta qui.
#
# Il tema si scrive in `localStorage` **prima** che la pagina si disegni,
# perche' e' li' che `avvio.js` va a leggerlo. Metterlo nel gancio in
# fondo al corpo vorrebbe dire fotografare il tema sbagliato e accorgersi
# del difetto di colore solo in casa — che e' come sono arrivate la #134,
# la #139 e la #152.
TEMA = """
<script>
(function () {
    var q = new URLSearchParams(location.search);
    var tema = q.get('tema');
    if (tema) { try { localStorage.setItem('shinra_theme_mode', tema); } catch (e) {} }
    var tavolozza = q.get('tavolozza');
    if (tavolozza) { try { localStorage.setItem('shinra_palette', tavolozza); } catch (e) {} }
})();
</script>
"""

GANCIO = """
<script>
window.addEventListener('load', function () {
    var q = new URLSearchParams(location.search);
    var scheda = q.get('scheda');
    if (scheda) setTimeout(function () { switchTab(scheda); }, 300);
    if (q.get('editor')) setTimeout(function () { openModularModeBuilder(); }, 700);
});
</script>
</body>"""


def prepara() -> None:
    if FUORI.exists():
        shutil.rmtree(FUORI)
    FUORI.mkdir()

    pagina = (percorsi.MODELLI_HTML / "index.html").read_text(encoding="utf-8")
    pagina = BLOCCHI.sub("", pagina)
    pagina = ESPRESSIONI.sub("anteprima", pagina)
    if "</body>" not in pagina:
        raise SystemExit("la pagina non ha piu' un </body>: il gancio delle schede non sa dove andare")
    if "<head>" not in pagina:
        raise SystemExit("la pagina non ha piu' un <head>: il gancio del tema non sa dove andare")
    pagina = pagina.replace("<head>", "<head>" + TEMA, 1)
    pagina = pagina.replace("</body>", GANCIO, 1)
    (FUORI / "index.html").write_text(pagina, encoding="utf-8")

    shutil.copytree(percorsi.STATICI, FUORI / "static")

    copioni = len(list((FUORI / "static" / "js").glob("*.js")))
    print(f"anteprima pronta in {FUORI} — {copioni} copioni")


if __name__ == "__main__":
    prepara()
    sys.exit(0)
