"""«Se la porta si apre dopo le 23, accendi l'ingresso.»

Fino a qui la casa era puramente reattiva: rispondeva quando le si parlava. Le
modalita' esistenti sono sequenze di azioni, non automazioni — si attivano
solo con una frase. Mancavano i trigger, e questo modulo li definisce.

Tre cose che questo dominio tiene ferme, e che sono la differenza fra
un'automazione utile e una che si disattiva dopo tre giorni:

**Un trigger su soglia scatta quando si attraversa, non mentre si sta
sotto.** «Avvisami se la temperatura scende sotto i 15» detto a una casa a 12
gradi non deve suonare a ogni lettura del sensore: deve suonare quando passa
da sopra a sotto. La differenza e' un avviso al giorno contro trecento, e
trecento avvisi al giorno diventano zero avvisi letti.

**Le condizioni si valutano al momento dello scatto, non a quello del
salvataggio.** Ovvio a dirsi, e la ragione per cui questo modulo e' puro:
riceve lo stato del mondo e non va a cercarselo, cosi' il momento e' scelto
da chi chiama e si puo' provare.

**Una regola che non scatta mai e una regola rotta si somigliano troppo.**
Per questo `perche_no()` dice quale condizione ha fermato l'esecuzione, e non
si limita a rispondere «no».

Qui non si esegue niente: entrano una regola, un evento e lo stato della casa,
esce «scatta» oppure «non scatta, per questo motivo».

Riferimento: issue #27.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping, Optional, Sequence

# --------------------------------------------------------------- i trigger

EVENTO = "evento"
STATO = "stato"
ORARIO = "orario"
ALBA = "alba"
TRAMONTO = "tramonto"

TRIGGER = (EVENTO, STATO, ORARIO, ALBA, TRAMONTO)

# I confronti di un trigger su stato. `attraversa_sotto` e `attraversa_sopra`
# sono i due che contano davvero: gli altri due scattano a ogni lettura che
# soddisfa la condizione, e vanno usati solo quando lo si vuole per davvero.
SOTTO = "sotto"
SOPRA = "sopra"
ATTRAVERSA_SOTTO = "attraversa_sotto"
ATTRAVERSA_SOPRA = "attraversa_sopra"
DIVENTA = "diventa"

CONFRONTI = (SOTTO, SOPRA, ATTRAVERSA_SOTTO, ATTRAVERSA_SOPRA, DIVENTA)

# ------------------------------------------------------------ le condizioni

FRA_LE_ORE = "fra_le_ore"
GIORNI = "giorni"
PRESENZA = "presenza"
STATO_ENTITA = "stato_entita"

CONDIZIONI = (FRA_LE_ORE, GIORNI, PRESENZA, STATO_ENTITA)

# ---------------------------------------------------------------- le azioni

AZIONE_MODALITA = "modalita"
AZIONE_DISPOSITIVO = "dispositivo"
AZIONE_AVVISO = "avviso"

AZIONI = (AZIONE_MODALITA, AZIONE_DISPOSITIVO, AZIONE_AVVISO)

# Quante regole di fila possono innescarsi a vicenda prima che si consideri
# un ciclo. Tre e' gia' generoso: una catena legittima piu' lunga di cosi'
# e' quasi sempre un errore di chi l'ha scritta.
PROFONDITA_MASSIMA = 3


class Ciclo(Exception):
    """Due o piu' regole si innescano a vicenda.

    Porta con se' la catena, perche' «una regola ha creato un ciclo» non
    aiuta nessuno a ripararlo: servono i nomi, in ordine.
    """

    def __init__(self, catena: Sequence[str]):
        self.catena = list(catena)
        super().__init__(" -> ".join(self.catena))


@dataclass(frozen=True)
class Regola:
    identificativo: str
    nome: str
    trigger: Mapping[str, Any]
    condizioni: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    azioni: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    attiva: bool = True


# ------------------------------------------------------------ i confronti


def _numero(valore: Any) -> Optional[float]:
    try:
        return float(valore)
    except (TypeError, ValueError):
        return None


def soglia_attraversata(confronto: str, precedente: Any, attuale: Any, soglia: Any) -> bool:
    """Il cuore del trigger su stato.

    `attraversa_sotto` e' vero solo nel momento del passaggio: prima sopra,
    adesso sotto. Se il valore precedente non e' un numero — la prima lettura
    dopo un riavvio, un sensore tornato da `unavailable` — l'attraversamento
    **non** si dichiara: non si sa da dove veniva, e inventarlo vorrebbe dire
    accendere il riscaldamento a ogni riavvio di Home Assistant.
    """
    adesso = _numero(attuale)
    limite = _numero(soglia)
    if adesso is None or limite is None:
        return False

    if confronto == SOTTO:
        return adesso < limite
    if confronto == SOPRA:
        return adesso > limite

    prima = _numero(precedente)
    if prima is None:
        return False

    if confronto == ATTRAVERSA_SOTTO:
        return prima >= limite > adesso
    if confronto == ATTRAVERSA_SOPRA:
        return prima <= limite < adesso

    return False


def _fra_le_ore(adesso: time, dalle: time, alle: time) -> bool:
    """Vero fra due ore, anche quando l'intervallo scavalca la mezzanotte.

    «Dalle 23 alle 6» e' la finestra piu' usata in una casa — la notte — ed
    e' proprio quella che un confronto ingenuo (`dalle <= adesso <= alle`)
    sbaglia sempre, perche' 23 non e' minore di 6.
    """
    if dalle <= alle:
        return dalle <= adesso <= alle
    return adesso >= dalle or adesso <= alle


def _ora(grezzo: Any, ripiego: time) -> time:
    if isinstance(grezzo, time):
        return grezzo
    try:
        pezzi = str(grezzo).split(":")
        return time(int(pezzi[0]), int(pezzi[1]) if len(pezzi) > 1 else 0)
    except (ValueError, IndexError):
        return ripiego


# ----------------------------------------------------------- gli scatti


def scatta_su_evento(regola: Regola, evento_tipo: str, dati: Mapping[str, Any]) -> bool:
    """Se questo evento fa scattare questa regola."""
    trigger = regola.trigger or {}
    tipo = str(trigger.get("tipo") or "")

    if tipo == EVENTO:
        if str(trigger.get("evento") or "") != evento_tipo:
            return False
        # Un trigger su evento puo' restringere a un'entita' o a un dominio:
        # «quando si apre una porta» non deve scattare per una lampadina.
        entita = str(trigger.get("entity_id") or "")
        if entita and str(dati.get("entity_id") or "") != entita:
            return False
        dominio = str(trigger.get("dominio") or "")
        if dominio and str(dati.get("dominio") or "") != dominio:
            return False
        atteso = trigger.get("stato")
        return atteso is None or str(dati.get("stato")) == str(atteso)

    if tipo == STATO:
        if str(dati.get("entity_id") or "") != str(trigger.get("entity_id") or ""):
            return False
        confronto = str(trigger.get("confronto") or ATTRAVERSA_SOTTO)
        if confronto == DIVENTA:
            # «diventa» e' un attraversamento fatto di parole: si dichiara
            # solo se lo stato e' cambiato davvero.
            return str(dati.get("stato")) == str(trigger.get("valore")) and str(
                dati.get("stato_precedente")
            ) != str(trigger.get("valore"))
        return soglia_attraversata(
            confronto, dati.get("stato_precedente"), dati.get("stato"), trigger.get("valore")
        )

    return False


# -------------------------------------------------------- le condizioni


def motivo_condizione(
    condizione: Mapping[str, Any],
    adesso: datetime,
    stati: Optional[Mapping[str, str]] = None,
    casa_abitata: Optional[bool] = None,
) -> Optional[str]:
    """Perche' **questa** condizione non e' soddisfatta, o `None` se lo e'.

    Sta da sola e non dentro il ciclo di `perche_no` perche' i nodi condizione
    dell'editor a grafo (issue #28) fanno la stessa domanda su una condizione
    per volta. Due implementazioni dello stesso vocabolario divergerebbero, e
    la divergenza si vedrebbe come «la stessa condizione si comporta in modo
    diverso a seconda di dove l'hai scritta».
    """
    tipo = str(condizione.get("tipo") or "")

    if tipo == FRA_LE_ORE:
        dalle = _ora(condizione.get("dalle"), time(0, 0))
        alle = _ora(condizione.get("alle"), time(23, 59))
        if not _fra_le_ore(adesso.time(), dalle, alle):
            return f"siamo fuori dalla fascia {dalle.strftime('%H:%M')}-{alle.strftime('%H:%M')}"

    elif tipo == GIORNI:
        giorni = [int(g) for g in (condizione.get("giorni") or []) if str(g).isdigit()]
        if giorni and adesso.weekday() not in giorni:
            return "oggi non e' uno dei giorni previsti"

    elif tipo == PRESENZA:
        vuole = bool(condizione.get("abitata", True))
        if casa_abitata is None:
            # Non sapere chi c'e' non e' sapere che non c'e' nessuno: una
            # regola che dipende dalla presenza non deve scattare al buio.
            return "non so se in casa c'e' qualcuno"
        if casa_abitata is not vuole:
            return "in casa c'e' qualcuno" if casa_abitata else "in casa non c'e' nessuno"

    elif tipo == STATO_ENTITA:
        entita = str(condizione.get("entity_id") or "")
        atteso = str(condizione.get("stato") or "")
        corrente = (stati or {}).get(entita)
        if corrente is None:
            return f"non conosco lo stato di {entita}"
        if str(corrente) != atteso:
            return f"{entita} e' {corrente} invece di {atteso}"

    return None


def perche_no(
    regola: Regola,
    adesso: datetime,
    stati: Optional[Mapping[str, str]] = None,
    casa_abitata: Optional[bool] = None,
) -> Optional[str]:
    """Quale condizione impedisce l'esecuzione, o `None` se nessuna.

    Torna il motivo e non un booleano perche' una regola che non scatta mai e
    una regola rotta si somigliano troppo: senza il motivo, chi la scrive puo'
    solo indovinare.
    """
    for condizione in regola.condizioni or ():
        motivo = motivo_condizione(condizione, adesso, stati, casa_abitata)
        if motivo:
            return motivo

    return None


def condizioni_soddisfatte(
    regola: Regola,
    adesso: datetime,
    stati: Optional[Mapping[str, str]] = None,
    casa_abitata: Optional[bool] = None,
) -> bool:
    return perche_no(regola, adesso, stati, casa_abitata) is None


# ------------------------------------------------------------- i cicli


def verifica_catena(catena: Sequence[str], prossima: str) -> list[str]:
    """La catena con la regola in piu', o `Ciclo` se si sta avvitando.

    Si guarda la catena vera e non solo un contatore di profondita': cosi'
    il messaggio puo' dire **quali** regole formano l'anello, che e' l'unica
    informazione con cui si ripara. «Una regola ha creato un ciclo» manda a
    leggerle tutte.
    """
    if prossima in catena:
        raise Ciclo([*catena, prossima])
    if len(catena) >= PROFONDITA_MASSIMA:
        raise Ciclo([*catena, prossima])
    return [*catena, prossima]


# ------------------------------------------------------------- gli orari


def prossimo_scatto(
    regola: Regola, adesso: datetime, tramonto: Optional[datetime] = None, alba: Optional[datetime] = None
) -> Optional[datetime]:
    """Quando questa regola a orario scattera' la prossima volta.

    `None` per le regole che non sono a orario: sono innescate dagli eventi e
    non hanno un «prossimo».
    """
    trigger = regola.trigger or {}
    tipo = str(trigger.get("tipo") or "")

    if tipo == ORARIO:
        quando = _ora(trigger.get("ora"), time(7, 0))
        giorni = [int(g) for g in (trigger.get("giorni") or []) if str(g).isdigit()]
        candidato = adesso.replace(hour=quando.hour, minute=quando.minute, second=0, microsecond=0)
        if candidato <= adesso:
            candidato += timedelta(days=1)
        if giorni:
            for _ in range(7):
                if candidato.weekday() in giorni:
                    break
                candidato += timedelta(days=1)
        return candidato

    if tipo in (ALBA, TRAMONTO):
        base = alba if tipo == ALBA else tramonto
        if base is None:
            return None
        scarto = int(trigger.get("scarto_minuti") or 0)
        return base + timedelta(minutes=scarto)

    return None


def descrivi_trigger(trigger: Mapping[str, Any]) -> str:
    """**Quando** scatta, a parole.

    Sta da sola perche' la stessa frase serve a due posti che non si
    conoscono: il nome di una regola generata da un nodo trigger dell'editor
    (issue #28) e la descrizione di una regola scritta a mano. Scriverla due
    volte vorrebbe dire che la stessa regola si chiama in due modi diversi a
    seconda di dove la si guarda.
    """
    tipo = str(trigger.get("tipo") or "")

    if tipo == ORARIO:
        return f"ogni giorno alle {_ora(trigger.get('ora'), time(7, 0)).strftime('%H:%M')}"
    if tipo == ALBA:
        return "all'alba"
    if tipo == TRAMONTO:
        return "al tramonto"
    if tipo == STATO:
        confronto = str(trigger.get("confronto") or "")
        verso = "scende sotto" if "sotto" in confronto else "sale sopra"
        if confronto == DIVENTA:
            verso = "diventa"
        return f"quando {trigger.get('entity_id')} {verso} {trigger.get('valore')}"
    return f"su {trigger.get('evento') or 'un evento'}"


def descrivi(regola: Regola) -> str:
    """La regola detta a parole, per il registro e per l'interfaccia."""
    quando_detto = descrivi_trigger(regola.trigger or {})
    quante = len(regola.azioni or ())
    return f"{regola.nome}: {quando_detto}, {quante} azion{'e' if quante == 1 else 'i'}"


def oggi_e(adesso: datetime) -> date:
    return adesso.date()
