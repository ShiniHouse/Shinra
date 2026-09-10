"""Chi ha parlato, e cosa comporta non saperlo.

Fino a qui il canale vocale non aveva identita'. La frase dell'ADR 0004 —
«chiunque si rivolga a un Echo agisce con l'identita' configurata nella
sessione» — era ottimista: l'identita' della sessione non arrivava ai
permessi. `registro.contesto().attore` restava vuoto per tutta la richiesta,
`permessi.profilo_corrente()` restituiva `None`, e `ha_permesso(None, ...)`
concede tutto. Non e' che a voce si agisse come l'amministratore: a voce
**non si veniva controllati affatto**.

Il pezzo mancante e' un'informazione che Amazon consegna gia', se in casa
sono configurati i profili vocali: `context.System.person.personId`, un
identificativo opaco e stabile della persona che ha parlato. Non e' una
password e non va trattata come tale — chi imita una voce puo' farsi
riconoscere — ma e' l'unico segnale di identita' che il canale offra, ed e'
enormemente meglio di niente.

**La regola che governa questo modulo: il silenzio non concede.** Una voce
che nessun profilo riconosce non e' «nessuna identita' in gioco», e' una
persona sconosciuta in casa. Le due cose portavano allo stesso risultato —
`None` — e quel risultato era «puo' fare tutto». Qui si separano.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

# Il ruolo di ricaduta quando non si sa chi parla. E' un nome di ruolo, non
# un insieme di permessi: cosi' chi ha ridisegnato i ruoli di casa decide
# anche questo, e chi cancella il ruolo resta senza permessi invece di
# ereditarli tutti (vedi `permessi.permessi_del_ruolo`).
RUOLO_DI_RICADUTA = "guest"

# Perche' l'identita' e' quella che e'. Finiscono nel registro e nelle
# risposte parlate: «non ti riconosco» e «non sei associato a un profilo»
# sono due problemi diversi, e si risolvono in modi diversi.
RICONOSCIUTA = "riconosciuta"
SENZA_PROFILI_VOCALI = "senza_profili_vocali"
VOCE_NON_ASSOCIATA = "voce_non_associata"
PROFILO_SPARITO = "profilo_sparito"


@dataclass(frozen=True)
class Identita:
    """Chi sta parlando, per quanto se ne possa sapere."""

    person_id: Optional[str] = None
    user_id: Optional[str] = None
    motivo: str = SENZA_PROFILI_VOCALI

    @property
    def riconosciuta(self) -> bool:
        """Vero solo quando si arriva a un profilo di casa.

        Sapere che «e' sempre la stessa voce» non basta: i permessi stanno
        sui ruoli, e un ruolo ce l'hanno i profili. Una voce nota ma non
        associata a nessuno vale quanto una sconosciuta.
        """
        return self.user_id is not None


def persona_dalla_richiesta(dati: Mapping[str, Any]) -> Optional[str]:
    """L'identificativo della persona che ha parlato, se Amazon lo manda.

    Sta in `context.System.person.personId`, e compare solo quando in casa
    sono configurati i profili vocali e Alexa ha riconosciuto la voce. Manca
    in tutti gli altri casi — compreso quando a parlare e' qualcuno di cui
    Alexa non ha il profilo — e mancare e' la condizione normale, non un
    errore.

    Da non confondere con `context.System.user.userId`, che identifica
    l'*account Amazon* di casa: e' lo stesso per tutti quelli che vivono qui,
    e usarlo come identita' vorrebbe dire ricreare esattamente il problema
    che questo modulo esiste per risolvere.
    """
    sistema = ((dati or {}).get("context") or {}).get("System") or {}
    persona = sistema.get("person") or {}
    identificativo = persona.get("personId")
    return str(identificativo) if identificativo else None


def risolvi(
    person_id: Optional[str],
    associazioni: Mapping[str, Optional[str]],
    profili_esistenti: Optional[Mapping[str, Any]] = None,
) -> Identita:
    """Da un identificativo vocale al profilo di casa, o alla ricaduta.

    `associazioni` va da `personId` al profilo Shinra. Un valore `None` vuol
    dire «questa voce l'abbiamo gia' sentita ma nessuno ha ancora detto di
    chi e'»: e' una riga utile — permette di associarla dalle impostazioni
    senza copiare identificativi a mano — ma non concede niente.

    `profili_esistenti` serve al caso in cui un profilo venga cancellato
    mentre un'associazione lo indica ancora. Senza il controllo, l'attore
    verrebbe impostato su un identificativo che non esiste piu', e
    `profilo_corrente()` tornerebbe `None`: cioe' cancellare un profilo
    riaprirebbe il buco. Con il controllo, quella voce torna sconosciuta.
    """
    if not person_id:
        return Identita(motivo=SENZA_PROFILI_VOCALI)

    if person_id not in associazioni:
        return Identita(person_id=person_id, motivo=VOCE_NON_ASSOCIATA)

    utente = associazioni.get(person_id)
    if not utente:
        return Identita(person_id=person_id, motivo=VOCE_NON_ASSOCIATA)

    if profili_esistenti is not None and utente not in profili_esistenti:
        return Identita(person_id=person_id, motivo=PROFILO_SPARITO)

    return Identita(person_id=person_id, user_id=utente, motivo=RICONOSCIUTA)


def spiega(identita: Identita, azione: str) -> str:
    """Come si dice a voce che non si puo'.

    Un rifiuto che non spiega si ripete: chi non capisce perche' riprova, e
    dopo tre tentativi conclude che l'impianto e' rotto. Ogni motivo ha il
    suo rimedio, e il rimedio va detto.
    """
    if identita.motivo == SENZA_PROFILI_VOCALI:
        return (
            f"Non {azione} da voce: non so chi sta parlando. Se configuri i profili "
            "vocali di Alexa e associ la tua voce dalle impostazioni, potro' farlo."
        )
    if identita.motivo == VOCE_NON_ASSOCIATA:
        return (
            f"Non {azione} da voce: riconosco la voce ma non so a chi corrisponde. "
            "Associala a un profilo dalle impostazioni."
        )
    if identita.motivo == PROFILO_SPARITO:
        return (
            f"Non {azione} da voce: la voce era associata a un profilo che non esiste "
            "piu'. Riassociala dalle impostazioni."
        )
    return f"Non {azione}."
