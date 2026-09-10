"""Le tabelle di Shinra.

**Sui nomi delle colonne.** Il progetto scrive in italiano il codice nuovo,
ma qui i nomi dei campi restano quelli di oggi — `text`, `category`,
`enabled`, `entity_id` — perche' non sono una scelta di stile: sono il
contratto che l'interfaccia web, le rotte HTTP e i file JSON esistenti gia'
usano. Tradurli qui vorrebbe dire aggiungere uno strato di conversione fra
database e API, cioe' un punto in piu' dove sbagliare durante una migrazione
che deve andare bene la prima volta. Le tabelle nuove, che non hanno un
passato, sono in italiano.

**Sugli identificativi.** Restano stringhe (`k_3f9a`, `timer_ab12`, `alessio`)
invece di diventare interi: sono gia' scritti nei file JSON, nei job dello
scheduler e nei cookie di sessione. Cambiarli renderebbe la migrazione una
riscrittura invece di una copia.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def adesso() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Utente(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="adult")
    age_group: Mapped[str] = mapped_column(String(32), default="adult")
    gender: Mapped[str] = mapped_column(String(32), default="unspecified")
    avatar_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Sempre cifrato: e' la regola stabilita dalla issue #3, non un'opzione.
    pin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_news_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    restricted_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    aggiornato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso, onupdate=adesso)


class Ruolo(Base):
    """Un insieme di permessi con un nome.

    I permessi appartengono al ruolo, non alla persona: cosi' se ne possono
    creare di nuovi — «Collaboratrice domestica», «Nonno», «Ospite fine
    settimana» — senza toccare il codice. `predefinito` marca i cinque che
    nascono con l'installazione: si possono modificare, non cancellare,
    perche' qualcuno ci e' assegnato.
    """

    __tablename__ = "ruoli"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descrizione: Mapped[Optional[str]] = mapped_column(Text, default="")
    permessi: Mapped[list[str]] = mapped_column(JSON, default=list)
    predefinito: Mapped[bool] = mapped_column(Boolean, default=False)


class Fatto(Base):
    """Un'informazione sulla casa, imparata o inserita a mano."""

    __tablename__ = "knowledge"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="generale", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)


class Alias(Base):
    """Il nome con cui una persona chiama un dispositivo di Home Assistant."""

    __tablename__ = "device_aliases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alias: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    room: Mapped[Optional[str]] = mapped_column(String(80), default="")
    domain: Mapped[Optional[str]] = mapped_column(String(40), default="light")


class Modalita(Base):
    """Una routine: «modalita' cinema» e le azioni che esegue."""

    __tablename__ = "modes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(40), default="zap")
    trigger_phrases: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[Optional[str]] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class Fonte(Base):
    """Una fonte di notizie."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="generale", index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Timer(Base):
    __tablename__ = "timers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(160), default="Timer")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[float] = mapped_column(Float, default=0.0)
    expires_at: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    # Nessun vincolo verso users: un timer creato da un ospite non registrato
    # deve sopravvivere, e cancellare una persona non deve far sparire i
    # timer che ha in corso in cucina.
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class Promemoria(Base):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class DispositivoFidato(Base):
    """Un telefono, un tablet, un computer che non deve richiedere il PIN.

    **Della credenziale si conserva solo l'impronta**, come per i PIN. Se un
    giorno il database finisse dove non deve, quelle righe non aprirebbero
    nessuna casa: l'originale ce l'ha soltanto il dispositivo, nel suo
    cookie.
    """

    __tablename__ = "dispositivi_fidati"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    impronta: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(120), default="Dispositivo")
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    ultimo_indirizzo: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class VoceRegistro(Base):
    """Una riga del registro delle azioni: chi ha fatto cosa, e com'e' andata.

    La tabella nasce qui, vuota, perche' lo schema iniziale la contenga: farla
    nascere dopo significherebbe una seconda migrazione sul database di una
    casa gia' in funzione. A scriverci sara' la issue #15; fino ad allora
    resta a zero righe, e si vede.
    """

    __tablename__ = "registro_azioni"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    momento: Mapped[datetime] = mapped_column(DateTime, default=adesso, index=True)
    # Nessun vincolo verso `users`, ed e' una decisione, non una svista. Un
    # registro deve poter scrivere chi ha agito **anche** se quella persona
    # non e' nell'anagrafica: un ospite che parla all'Echo, un profilo
    # cancellato dopo il fatto. Con la chiave esterna quelle righe venivano
    # rifiutate dal database — cioe' proprio le azioni che piu' interessa
    # ritrovare sparivano, e in silenzio, perche' il registro non solleva.
    attore: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    canale: Mapped[str] = mapped_column(String(32), default="")
    azione: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dettagli: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    esito: Mapped[str] = mapped_column(String(32), default="")
    # Quanto e' durata, e a quale richiesta apparteneva. La correlazione lega
    # fra loro le righe di un unico turno: «accendi le luci di sotto» puo'
    # produrre tre comandi, e senza un filo comune sembrano tre eventi
    # scollegati avvenuti nello stesso secondo.
    durata_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    correlazione: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)


class LetturaEnergia(Base):
    """Un contatore di energia a un istante, come lo segnava Home Assistant.

    Si conserva la **lettura grezza**, non il consumo gia' calcolato. E' una
    scelta e vale la pena dire perche': il consumo di un'ora e' una
    differenza fra due letture, e le differenze si possono ricalcolare mentre
    le letture perdute non tornano. Se domani si scopre che i salti dei
    contatori vanno trattati diversamente — e succedera', perche' ogni
    integrazione ne ha di suoi — con le letture in archivio si rifa' il
    conto su tutto lo storico; con i consumi si e' cristallizzato l'errore.

    La fascia invece **si scrive**, anche se sarebbe ricalcolabile dal
    momento: ARERA puo' cambiare gli orari, e una bolletta di due anni fa
    deve restare divisa come lo era allora, non come lo sarebbe oggi.

    Riferimento: issue #24.
    """

    __tablename__ = "letture_energia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    momento: Mapped[datetime] = mapped_column(DateTime, default=adesso, index=True)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    # Il valore del contatore, in kilowattora, cosi' come lo segnava.
    valore: Mapped[float] = mapped_column(Float, nullable=False)
    # Quanto e' stato consumato dalla lettura precedente. Ridondante rispetto
    # alle letture, e tenuto lo stesso: serve a interrogare lo storico senza
    # rileggere tutta la tabella per fare una sottrazione.
    consumo: Mapped[float] = mapped_column(Float, default=0.0)
    fascia: Mapped[str] = mapped_column(String(4), default="", index=True)


class Lista(Base):
    """Una lista di casa, per chi non ha le `todo` di Home Assistant.

    Esiste solo come alternativa: quando in Home Assistant c'e' una lista
    `todo` che corrisponde, si scrive li' e questa tabella resta vuota. Una
    copia sincronizzata sarebbe due verita' che divergono al primo conflitto,
    e una lista della spesa sbagliata e' peggio di nessuna lista, perche' ci
    si va al supermercato.

    Riferimento: issue #25.
    """

    __tablename__ = "liste"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    creata_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)


class VoceLista(Base):
    """Una riga di una lista."""

    __tablename__ = "voci_lista"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lista_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    testo: Mapped[str] = mapped_column(String(240), nullable=False)
    fatta: Mapped[bool] = mapped_column(Boolean, default=False)
    # Chi l'ha aggiunta. Senza vincolo verso `users`, come nel registro: un
    # ospite che detta la spesa all'Echo non e' nell'anagrafica, e la sua
    # riga non deve sparire per questo.
    autore: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    aggiunta_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)


class EventoCalendario(Base):
    """Un impegno segnato in casa, per chi non ha calendari in Home Assistant.

    Come per le liste: e' l'alternativa, non una copia. Dove c'e'
    `calendar.qualcosa`, gli eventi si leggono di li'.
    """

    __tablename__ = "eventi_calendario"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    titolo: Mapped[str] = mapped_column(String(240), nullable=False)
    inizio: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    fine: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tutto_il_giorno: Mapped[bool] = mapped_column(Boolean, default=False)
    luogo: Mapped[str] = mapped_column(String(160), default="")
    autore: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class ScadenzaManutenzione(Base):
    """Filtri della caldaia, revisione, bollo, garanzie.

    `documento` e' un riferimento, non un file: dove sta la garanzia, il
    numero della fattura, un percorso. Conservare gli allegati vorrebbe dire
    caricamento, spazio disco e backup — una funzione sua, non una riga di
    questa tabella, e prometterla qui con un campo di testo sarebbe peggio
    che non averla.

    Riferimento: issue #25.
    """

    __tablename__ = "scadenze"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    titolo: Mapped[str] = mapped_column(String(240), nullable=False)
    prossima: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # Zero significa «non torna»: una garanzia scade una volta sola.
    ogni: Mapped[int] = mapped_column(Integer, default=0)
    unita: Mapped[str] = mapped_column(String(16), default="mesi")
    preavviso: Mapped[int] = mapped_column(Integer, default=7)
    documento: Mapped[str] = mapped_column(String(500), default="")
    ultima_fatta: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Il promemoria gia' creato per questa scadenza, per non crearne uno
    # nuovo a ogni giro del controllo quotidiano.
    promemoria_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class SottoscrizionePush(Base):
    """Un telefono che ha detto «avvisami», con le chiavi per raggiungerlo.

    L'`endpoint` e' un indirizzo scelto dal browser presso il suo servizio
    push (Google, Mozilla, Apple): e' l'identificativo naturale della
    sottoscrizione, e due sottoscrizioni con lo stesso endpoint sono lo
    stesso telefono che si e' ri-registrato.

    Le chiavi `p256dh` e `auth` servono a cifrare il contenuto **prima** che
    esca da qui: il servizio push instrada la busta e non puo' leggerla. E'
    il motivo per cui un promemoria puo' passare da Google senza che Google
    sappia cosa dice.

    Riferimento: issue #29.
    """

    __tablename__ = "sottoscrizioni_push"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), default="Dispositivo")
    creata_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    ultimo_invio: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Quanti invii di fila sono falliti. Una sottoscrizione revocata dal
    # browser risponde 404 o 410 e va tolta subito; un errore di rete e'
    # un'altra cosa e non deve far perdere il telefono di nessuno.
    fallimenti: Mapped[int] = mapped_column(Integer, default=0)


class PreferenzaNotifica(Base):
    """Cosa una persona vuole ricevere, e dove.

    Una riga per preferenza invece di una colonna per categoria: le
    categorie cambiano a ogni funzione nuova, e una tabella che cambia forma
    a ogni funzione nuova e' una migrazione a ogni funzione nuova.
    """

    __tablename__ = "preferenze_notifiche"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # `silenzioso`, `canale.push`, `categoria.energia`...
    chiave: Mapped[str] = mapped_column(String(64), nullable=False)
    valore: Mapped[bool] = mapped_column(Boolean, default=True)


class Regola(Base):
    """Un'automazione: quando succede questo, se vale quest'altro, fai questo.

    Trigger, condizioni e azioni stanno in JSON e non in colonne, ed e' una
    scelta: le forme che possono assumere cambiano a ogni tipo di trigger
    nuovo, e una tabella che cambia forma a ogni tipo nuovo e' una migrazione
    a ogni tipo nuovo. Il prezzo e' che il database non li valida — li valida
    `domain/regole.py`, che e' anche l'unico posto dove ha senso farlo.

    Riferimento: issue #27.
    """

    __tablename__ = "regole"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    attiva: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    trigger: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    condizioni: Mapped[list[Any]] = mapped_column(JSON, default=list)
    azioni: Mapped[list[Any]] = mapped_column(JSON, default=list)
    creata_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    autore: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Quando e come e' andata l'ultima volta. Ridondante rispetto al registro
    # e tenuto lo stesso: e' la prima cosa che si guarda quando una regola
    # «non funziona», e cercarla nel registro richiede di sapere gia' quando
    # sarebbe dovuta scattare.
    ultimo_scatto: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ultimo_esito: Mapped[str] = mapped_column(String(200), default="")


class EmbeddingFatto(Base):
    """Il vettore di un fatto, con l'impronta del testo da cui e' nato.

    L'impronta e' la parte che fa lavorare il ricalcolo da solo: se il testo
    del fatto cambia, l'impronta salvata non corrisponde piu' e il vettore
    viene rifatto — senza che nessuno debba ricordarsi di chiamare qualcosa
    quando modifica un fatto. Un vettore vecchio non da' errore: da' risposte
    sbagliate, che e' peggio.

    Anche il nome del modello e' salvato: cambiare modello di embedding
    cambia lo spazio vettoriale, e confrontare vettori di due modelli diversi
    produce numeri che sembrano punteggi e non lo sono.

    Riferimento: issue #32.
    """

    __tablename__ = "embedding_fatti"

    fatto_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vettore: Mapped[list[Any]] = mapped_column(JSON, default=list)
    modello: Mapped[str] = mapped_column(String(120), default="")
    impronta: Mapped[str] = mapped_column(String(64), default="", index=True)
    calcolato_il: Mapped[datetime] = mapped_column(DateTime, default=adesso)


class VoceSentita(Base):
    """Una voce che ha parlato a un Echo, associata o no a un profilo.

    Il nome dice cio' che la tabella contiene davvero: voci *sentite*, non
    voci riconosciute. Una riga con `user_id` vuoto e' una voce che Alexa
    distingue ma che in casa nessuno ha ancora dichiarato di chi sia — e non
    concede niente. Esiste perche' altrimenti associarla vorrebbe dire
    copiare a mano un identificativo opaco preso da un log.

    `person_id` e' l'identificativo che Amazon assegna a un profilo vocale:
    opaco, stabile, e privo di significato fuori da questa casa. Non e' un
    dato anagrafico e non contiene il nome di nessuno.

    Riferimento: issue #48.
    """

    __tablename__ = "voci_sentite"

    person_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    # Vuoto finche' qualcuno non dice di chi e' questa voce.
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    # Un'etichetta scritta a mano dalle impostazioni («la voce delle 8 del
    # mattino»), per distinguere due righe sconosciute fra loro.
    nota: Mapped[str] = mapped_column(String(200), default="")
    prima_volta: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    ultima_volta: Mapped[datetime] = mapped_column(DateTime, default=adesso)
    # Quante richieste sono arrivate da questa voce. Serve a scegliere quale
    # associare per prima: quella che parla ogni giorno e' di casa.
    quante_volte: Mapped[int] = mapped_column(Integer, default=0)
