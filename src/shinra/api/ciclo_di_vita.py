"""Il ciclo di vita del servizio: cosa si prepara all'avvio e cosa si ferma allo spegnimento.

Stava in `app.py`, che superava le settecento righe (issue #196). Nessuno di
questi passi puo' impedire l'avvio: un hub domotico che si rifiuta di partire
lascia una casa senza controllo, quindi i problemi si segnalano nel log e si
va avanti.
"""

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shinra.api import sicurezza
from shinra.config.settings import (
    assicura_segreto_sessione,
    migra_segreti_su_env,
    settings,
    verifica_configurazione,
)
from shinra.infra.homeassistant.client import client_home_assistant
from shinra.infra.scheduler.motore import scheduler
from shinra.services import eventi_casa, permessi, registro
from shinra.services.allarme import allarme
from shinra.services.conoscenza import servizio_conoscenza
from shinra.services.consegna import registra_canali
from shinra.services.energia import servizio_energia
from shinra.services.manutenzione import servizio_manutenzione
from shinra.services.notifiche import servizio_notifiche
from shinra.services.presenza import presenza
from shinra.services.regole import motore_regole
from shinra.services.salvataggio import servizio_salvataggio
from shinra.services.simulazione import servizio_simulazione
from shinra.services.timer_engine import timer_engine
from shinra.services.trascrizione import servizio_trascrizione
from shinra.services.user_manager import user_manager

# I lavori di avvio che girano in sottofondo. Tenerne un riferimento e'
# necessario: `asyncio` non lo fa, e un task non referenziato puo'
# sparire a meta'.
_in_sottofondo: set = set()

logger = logging.getLogger("Shinra")


def _prepara_accesso() -> None:
    """Fa in modo che al primo avvio esista un modo per entrare.

    Con l'autenticazione attiva e nessun PIN configurato, imporre la
    protezione chiuderebbe fuori tutti — e in una casa questo significa
    restare senza controllo su luci e riscaldamento. Qui succedono due cose:

    - un PIN in chiaro rimasto in configurazione da una versione precedente
      viene trasferito sull'amministratore e cifrato;
    - se non esiste alcun PIN, ne viene generato uno e scritto nel log una
      volta sola, perche' il proprietario possa entrare e cambiarlo.
    """
    if not settings.security.auth_enabled:
        logger.warning(
            "Autenticazione disattivata: chiunque sia sulla rete puo' comandare "
            "l'impianto e leggere i dati della famiglia. Attivala dalle impostazioni."
        )
        return

    utenti = user_manager.get_users()
    if not utenti:
        return

    # Un PIN in chiaro rimasto sul profilo da una versione precedente non
    # verrebbe mai riconosciuto: il confronto si aspetta un hash. Va cifrato
    # qui, altrimenti risulta "presente" e blocca la generazione, lasciando
    # chiusa fuori tutta la famiglia.
    migrati = [
        u.name
        for u in utenti
        if u.pin and not sicurezza.e_cifrato(u.pin) and user_manager.imposta_pin(u.id, u.pin)
    ]
    if migrati:
        logger.warning(
            "PIN cifrati per: %s. Restano quelli di prima, ora non piu' leggibili sul disco.",
            ", ".join(migrati),
        )
        utenti = user_manager.get_users()

    if any(sicurezza.e_cifrato(u.pin) for u in utenti):
        return

    amministratore = next((u for u in utenti if u.role == "admin"), utenti[0])

    pin_ereditato = (settings.security.admin_pin or "").strip()
    if pin_ereditato:
        user_manager.imposta_pin(amministratore.id, pin_ereditato)
        logger.warning(
            "Il PIN di %s e' stato preso dalla configurazione e cifrato. "
            "Da ora ogni familiare ha il proprio PIN.",
            amministratore.name,
        )
        return

    pin_nuovo = f"{secrets.randbelow(1_000_000):06d}"
    user_manager.imposta_pin(amministratore.id, pin_nuovo)
    logger.warning(
        "=== PRIMO ACCESSO ===  PIN per %s: %s  "
        "Compare solo in questo messaggio: annotalo e cambialo dalle impostazioni.",
        amministratore.name,
        pin_nuovo,
    )


def _pulisci_registro() -> None:
    """Eseguita una volta al giorno dallo scheduler.

    Qui sopra c'era `@asynccontextmanager`, finito per sbaglio su questa
    funzione invece che su `lifespan`, due definizioni piu' in basso. Non
    faceva rumore: lo scheduler chiamava la funzione, riceveva un gestore di
    contesto e lo buttava via — **il corpo non e' mai stato eseguito**. Il
    registro delle azioni non e' mai stato ripulito da quando questa riga
    esiste, e su un hub domotico e' una tabella che cresce a ogni comando.

    Un decoratore fuori posto non da' errore, non da' avviso e non si vede
    rileggendo: la funzione e' li', il lavoro e' programmato, il log tace.
    """
    registro.pulisci(settings.registro.retention_days)


def _prepara_archivio() -> None:
    """Allinea lo schema e, la prima volta, semina la casa con i dati di esempio.

    La semina avviene solo se il database e' completamente vuoto: cosi'
    riavviare il servizio non riporta mai indietro dati cancellati nel
    frattempo.

    Se qualcosa va storto non si blocca l'avvio: una casa senza controllo e'
    peggio di una casa con l'anagrafica vecchia. Il problema finisce nel log
    e resta visibile.
    """
    from shinra.infra.db import importazione

    try:
        importazione.applica_migrazioni()
        importati = importazione.semina_se_vuoto()
        # I ruoli nascono qui, dopo lo schema e dopo l'eventuale semina:
        # i loro identificativi coincidono con i valori che il campo `role` ha
        # gia' nei profili, quindi chi aggiorna si ritrova gia' assegnato.
        creati = permessi.assicura_ruoli_predefiniti()
        if creati:
            logger.info("Ruoli predefiniti creati: %s", ", ".join(creati))
        if importati:
            logger.info("Casa nuova: seminate %d voci dai dati di esempio.", sum(importati.values()))
    except Exception as e:
        logger.error("Preparazione del database non riuscita: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Controlli e migrazioni all'avvio.

    Nessuno di questi passi puo' impedire l'avvio: un hub domotico che si
    rifiuta di partire lascia una casa senza controllo. I problemi vengono
    segnalati con chiarezza nel log e restano visibili.
    """
    migrati = migra_segreti_su_env()
    if migrati:
        logger.warning(
            "Segreti spostati da config.yaml a .env: %s. "
            "Se config.yaml e' mai finito in un commit, revoca subito quelle credenziali.",
            ", ".join(migrati),
        )

    if assicura_segreto_sessione():
        logger.info("Generato il segreto di sessione di questa installazione.")

    # Il database prima di tutto il resto: sotto ci sono l'anagrafica, i
    # timer e la conoscenza di casa, e ogni passo che segue li legge.
    _prepara_archivio()

    _prepara_accesso()

    # Scheduler: da qui timer e promemoria scattano lato server, anche a
    # browser chiuso e attraverso i riavvii.
    scheduler.avvia()

    # La casa che dice cosa succede. Parte in sottofondo e non blocca
    # l'avvio: se Home Assistant non risponde, il servizio deve partire lo
    # stesso e funzionare in modo ridotto — e' una casa, non un datacenter.
    await eventi_casa.avvia()

    # Chi c'e' in casa. Dopo la connessione agli eventi, perche' la prima
    # fotografia la legge dalla cache che quella riempie.
    await presenza.avvia()

    # L'allarme che scatta mentre nessuno guarda la dashboard non ha
    # avvisato nessuno: qui almeno diventa un evento sul bus.
    allarme.avvia()

    # La simulazione di presenza si spegne da sola quando qualcuno rientra:
    # senza questo ascolto continuerebbe ad accendere e spegnere le luci
    # addosso a chi ci vive.
    servizio_simulazione.avvia()

    # I contatori: Home Assistant tiene lo stato di adesso, non quello di
    # ieri. Se nessuno annota le letture, «quanto ho consumato la settimana
    # scorsa» non ha risposta possibile (issue #24).
    servizio_energia.avvia()

    # Le scadenze di casa diventano promemoria che suonano. Senza questo
    # sarebbero un elenco che aspetta di essere aperto, cioe' un elenco
    # dimenticato (issue #25).
    servizio_manutenzione.avvia()

    # Un archivio della configurazione al giorno, senza doversene ricordare:
    # un backup che bisogna ricordarsi di fare e' un backup che non esiste
    # (issue #35). Non i dati, solo cio' che costerebbe ore rifare.
    servizio_salvataggio.avvia()

    # Il canale verso il telefono. Fino alla #29 `casa.intrusione` veniva
    # pubblicato e non lo ascoltava nessuno: un allarme che scatta mentre
    # nessuno guarda non ha avvisato nessuno.
    servizio_notifiche.avvia()

    # Le regole: la casa smette di aspettare la domanda. Dopo le
    # notifiche, perche' un ciclo fra regole va fermato **e** raccontato,
    # e raccontarlo richiede un canale (issue #27).
    motore_regole.avvia()

    # L'indice della conoscenza, in sottofondo: senza embedding il recupero
    # resta testuale, quindi non blocca l'avvio (issue #32).
    #
    # Il riferimento si tiene: un task senza qualcuno che lo guardi puo'
    # essere raccolto dal garbage collector a meta' del lavoro, e l'indice
    # resterebbe fatto per meta' senza che niente lo dica.
    indicizzazione = asyncio.create_task(servizio_conoscenza.aggiorna_indice())
    _in_sottofondo.add(indicizzazione)
    indicizzazione.add_done_callback(_in_sottofondo.discard)

    # Il modello di trascrizione, in sottofondo. La prima volta i pesi si
    # scaricano e possono volerci minuti: se quel tempo lo paga la prima
    # persona che preme il microfono, la sua richiesta resta aperta finche'
    # qualcosa davanti al server non la taglia — Cloudflare a cento secondi,
    # con un 524 che non spiega niente. Qui non sta aspettando nessuno
    # (issue #31).
    #
    # Lo stato si scrive nel log **sempre**, anche quando non c'e' niente da
    # fare. Un ramo che decide di non fare niente in silenzio e' esattamente
    # cio' che ha reso impossibile capire, dal log di casa, perche' il
    # microfono non trascrivesse: non sapere se la preparazione non fosse
    # partita, o fosse partita e morta, costringe a indovinare.
    voce = servizio_trascrizione.per_l_interfaccia()
    logger.info(
        "Voce: motore=%s pronto=%s modello=%s gia_in_memoria=%s",
        voce["motore"],
        voce["pronto"],
        voce["modello"] or "-",
        voce["modello_caricato"],
    )
    if servizio_trascrizione.prepara():
        logger.info("Preparo il modello di trascrizione in sottofondo.")

    registra_canali()
    ripresi = timer_engine.ripristina_job()
    rimossi = timer_engine.pulisci_scaduti()
    if any(ripresi.values()) or rimossi:
        logger.info(
            "Ripresi %d timer e %d promemoria; rimossi %d timer scaduti.",
            ripresi["timer"],
            ripresi["promemoria"],
            rimossi,
        )

    # Registro delle azioni: log strutturato e pulizia periodica.
    if settings.registro.enabled:
        percorso = registro.configura_log_json()
        if percorso:
            logger.info("Log strutturato in %s", percorso)
        giorni = settings.registro.retention_days
        if giorni > 0:
            scheduler.programma_periodico("registro.pulizia", _pulisci_registro, ore=24)
            registro.pulisci(giorni)

    for problema in verifica_configurazione():
        logger.warning("Configurazione: %s", problema)

    yield

    # Spegnimento: i job restano nell'archivio per la prossima accensione.
    scheduler.ferma()
    motore_regole.ferma()
    servizio_notifiche.ferma()
    servizio_salvataggio.ferma()
    servizio_manutenzione.ferma()
    servizio_energia.ferma()
    servizio_simulazione.ferma()
    allarme.ferma()
    await presenza.ferma()
    await eventi_casa.ferma()
    await client_home_assistant().chiudi()
