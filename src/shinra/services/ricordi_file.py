"""I ricordi come file Markdown: esportare, rileggere con un'anteprima, applicare solo dopo la conferma (#251).

Il database resta la fonte; il file e' una vista. Qui non c'e' nessuna sincronizzazione: si esporta quando lo si chiede, si
rilegge quando lo si chiede, e prima di scrivere si guarda cosa cambierebbe.

Le regole che i test difendono:

- **il perimetro e' di chi importa**: si esportano e si rileggono solo i ricordi dell'ambito scelto (i propri privati, oppure
  quelli della casa) che chi importa puo' gia' modificare. Un identificativo di un altro profilo, o inventato, non tocca
  niente: la riga e' un ricordo nuovo, nel proprio ambito;
- **niente scritture silenziose**: `anteprima` non scrive; `applica` ricalcola la differenza sul server (non si fida di
  quella mostrata) e scrive solo con la conferma. Cio' che manca dal file e' *proposto* come tolto e, se la persona lo
  conferma, **archiviato** (non cancellato: si riattiva);
- **un testo con la forma di un ordine non nasce attivo**: un ricordo nuovo o modificato che non ha la forma di un ricordo
  (`avvelenamento.valuta`) entra come *proposto* e resta fuori dal prompt finche' una persona non lo accetta;
- **tetti**: un file troppo grande o con troppe righe e' rifiutato prima di leggerlo;
- il registro dice quanti ricordi, mai quali ne' cosa dicono.
"""

from __future__ import annotations

from typing import Any, Mapping

from shinra.domain import avvelenamento, memorie_md
from shinra.domain import ricordi as regole
from shinra.infra.db import depositi
from shinra.infra.lingue import schemi
from shinra.services import registro, ricordi

FILE_MASSIMO_CARATTERI = 200_000
VOCI_MASSIME = 500
ORIGINE_IMPORTATO = "importato"


def _perimetro(profilo: Any, ambito: str, solo_modificabili: bool) -> list[dict[str, Any]]:
    if ambito not in ("casa", "mio"):
        raise ricordi.DatoNonValido("ambito: casa oppure mio")
    chi = ricordi._id(profilo)
    if ambito == "mio" and not chi:
        raise ricordi.NonConsentito("Serve un profilo per i propri ricordi.")
    trovati = []
    for r in depositi.fatti.elenco():
        if not regole.e_visibile_a(r, chi):
            continue
        if regole.e_della_casa(r) != (ambito == "casa"):
            continue
        if r.get("stato", regole.STATO_ATTIVO) == regole.STATO_ARCHIVIATO:
            continue
        if solo_modificabili and not ricordi._puo_toccare(profilo, r):
            continue
        trovati.append(r)
    return trovati


def esporta(profilo: Any, ambito: str) -> str:
    """Il Markdown dei ricordi di questo ambito che chi chiede vede. Contiene dati personali, e lo dice."""
    testo = memorie_md.esporta(_perimetro(profilo, ambito, solo_modificabili=False))
    registro.registra("ricordi.esportati", dettagli={"ambito": ambito})
    return testo


def _controlla_il_file(contenuto: str) -> None:
    if not isinstance(contenuto, str) or not contenuto.strip():
        raise ricordi.DatoNonValido("il file e' vuoto")
    if len(contenuto) > FILE_MASSIMO_CARATTERI:
        raise ricordi.DatoNonValido(
            f"il file e' troppo grande (al massimo {FILE_MASSIMO_CARATTERI} caratteri)"
        )
    voci, _ = memorie_md.leggi(contenuto)
    if len(voci) > VOCI_MASSIME:
        raise ricordi.DatoNonValido(f"il file ha troppi ricordi (al massimo {VOCI_MASSIME})")


def _sospetta(profilo: Any, testo: str) -> bool:
    sospetti = schemi(getattr(profilo, "lingua", "") or "").sospetto
    return not avvelenamento.valuta(testo, sospetti).ammesso


def _come_si_mostra(r: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "testo": r.get("text", ""),
        "categoria": r.get("category", "generale"),
        "attivo": bool(r.get("enabled", True)),
    }


def _differenze(profilo: Any, ambito: str, contenuto: str) -> memorie_md.Differenze:
    _controlla_il_file(contenuto)
    return memorie_md.confronta(contenuto, _perimetro(profilo, ambito, solo_modificabili=True))


def anteprima(profilo: Any, ambito: str, contenuto: str) -> dict[str, Any]:
    """Cosa cambierebbe rileggendo il file. **Non scrive niente.**"""
    d = _differenze(profilo, ambito, contenuto)
    return {
        "nuovi": [
            {
                "testo": v.testo,
                "categoria": v.categoria,
                "attivo": v.attivo,
                "sospetto": _sospetta(profilo, v.testo),
            }
            for v in d.nuovi
        ],
        "modificati": [
            {
                "id": str(prima["id"]),
                "prima": _come_si_mostra(prima),
                "dopo": {"testo": v.testo, "categoria": v.categoria, "attivo": v.attivo},
                "sospetto": _sospetta(profilo, v.testo),
            }
            for prima, v in d.modificati
        ],
        "tolti": [{"id": str(f["id"]), **_come_si_mostra(f)} for f in d.tolti],
        "invariati": d.invariati,
        "ignorate": d.ignorate,
    }


def applica(profilo: Any, ambito: str, contenuto: str, conferma: bool, togli: bool = False) -> dict[str, int]:
    """Scrive la differenza, **solo con la conferma**. Ricalcolata qui: non si applica quella che l'anteprima ha mostrato."""
    if not conferma:
        raise ricordi.DatoNonValido("serve la conferma, dopo aver guardato l'anteprima")
    d = _differenze(profilo, ambito, contenuto)
    fatti = {"nuovi": 0, "modificati": 0, "archiviati": 0, "saltati": 0, "da_confermare": 0}

    for voce in d.nuovi:
        try:
            creato = ricordi.crea(profilo, voce.testo, voce.categoria, ambito)
        except ricordi.DatoNonValido:
            fatti["saltati"] += 1
            continue
        campi: dict[str, Any] = {"origine": ORIGINE_IMPORTATO, "enabled": voce.attivo}
        if _sospetta(profilo, voce.testo):
            campi["stato"] = regole.STATO_PROPOSTO
            fatti["da_confermare"] += 1
        depositi.fatti.aggiorna(creato["id"], campi)
        fatti["nuovi"] += 1

    for prima, voce in d.modificati:
        campi = {"text": voce.testo, "category": voce.categoria, "enabled": voce.attivo}
        if _sospetta(profilo, voce.testo):
            campi["stato"] = regole.STATO_PROPOSTO
            fatti["da_confermare"] += 1
        try:
            ricordi.modifica(profilo, str(prima["id"]), campi)
        except ricordi.DatoNonValido:
            fatti["saltati"] += 1
            continue
        fatti["modificati"] += 1

    if togli:
        for f in d.tolti:
            ricordi.modifica(profilo, str(f["id"]), {"stato": regole.STATO_ARCHIVIATO})
            fatti["archiviati"] += 1

    registro.registra("ricordi.importati", dettagli={"ambito": ambito, **fatti})
    return fatti
