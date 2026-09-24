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

La pagina si compone chiedendolo a Jinja, non cancellando i tag con
un'espressione regolare. Fino alla #176 si faceva cosi', e finche' i
blocchi erano commenti e condizioni bastava — con due trappole gia'
pagate: il segnaposto senza DOTALL e senza graffe annidate, perche' la
prima versione mangiava cinquantaquattro caratteri di JavaScript vero
fra la prima `{{` e la `}}` piu' vicina, e la pagina si apriva con il
copione morto.

Dalla #176 `{% include %}` porta dentro nove file di markup: cancellarlo
darebbe una dashboard che si apre, risponde, e non ha nessuna scheda
dentro — e i test dei gesti direbbero che il pulsante non c'e', il che
sarebbe anche vero.
"""

from __future__ import annotations

import shutil
import sys
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from shinra import percorsi

FUORI = percorsi.RADICE / ".anteprima"

# Una versione finta al posto di quella vera: l'anteprima non esce da un
# checkout con un tag, e il riquadro della versione nell'intestazione deve
# comunque esserci, perche' i gesti misurano anche la barra.
VERSIONE = SimpleNamespace(descrizione="anteprima", ramo="anteprima", commit="anteprima")

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

    ambiente = Environment(loader=FileSystemLoader(str(percorsi.MODELLI_HTML)), autoescape=True)
    pagina = ambiente.get_template("index.html").render(versione=VERSIONE)

    if "{% include" in pagina:
        raise SystemExit("la pagina composta porta ancora un include: qualcosa non e' stato reso")
    # Il controllo che sarebbe servito alla #176: una pagina senza schede si
    # apre, risponde e sembra viva. I gesti direbbero «il pulsante non c'e'»,
    # ed e' il genere di messaggio che manda a cercare nel posto sbagliato.
    schede = pagina.count('class="tab-content')
    if schede < 6:
        raise SystemExit(f"la pagina composta ha {schede} schede: i pezzi inclusi non sono entrati")
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
