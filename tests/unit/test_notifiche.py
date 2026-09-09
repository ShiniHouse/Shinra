"""Le notifiche: chi viene avvisato, come, e cosa non si puo' zittire.

Il difetto da cui nasce la funzione: `casa.intrusione` veniva pubblicato da
`services/allarme.py` e **non lo ascoltava nessuno** — non il WebSocket della
dashboard, non `services/consegna.py`, niente nell'interfaccia. Le note della
`v0.3.0` dicevano che almeno alla dashboard arrivava, e non era vero. Un
allarme che scatta mentre nessuno guarda non ha avvisato nessuno.

Le due regole che i test qui difendono:

**La priorita' non e' un'etichetta, e' un permesso.** Un'intrusione suona
anche a silenzioso attivo; un avviso energetico no. Se il silenzioso potesse
spegnere un allarme, sarebbe un modo per spegnere l'allarme dimenticandosene.

**Il canale sbagliato e' peggio del canale mancante.** Un'intrusione
annunciata ad alta voce in casa avvisa chi e' dentro — eventualmente il ladro
— e non avvisa chi e' fuori.

Nessun test manda una notifica vera: si verifica cosa verrebbe mandato, a chi,
e su quale canale.

Riferimento: issue #29.
"""

from __future__ import annotations

import pytest

from shinra.domain import notifiche as dominio
from shinra.domain.eventi import CASA_INTRUSIONE, PROMEMORIA_SCADUTO, TIMER_SCADUTO, Evento
from shinra.infra.db import depositi
from shinra.services import notifiche as servizio_modulo
from shinra.services.notifiche import ServizioNotifiche

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


@pytest.fixture
def push_finto(monkeypatch):
    """Il mittente push che annota invece di spedire."""
    from shinra.infra.push import mittente

    inviati: list[tuple[str, dict]] = []
    esito = {"riuscito": True, "stato": 201}

    def finto_invia(sottoscrizione, carico):
        inviati.append((str(sottoscrizione.get("endpoint")), dict(carico)))
        return mittente.Esito(esito["riuscito"], stato=esito["stato"], errore="finto")

    monkeypatch.setattr(mittente, "invia", finto_invia)
    return inviati, esito


@pytest.fixture
def con_telefono(push_finto):
    servizio = ServizioNotifiche()
    servizio.registra_dispositivo("alessio", ENDPOINT, "chiave-p256dh", "chiave-auth", "Telefono")
    return servizio


# ============================================ le priorita' e il silenzioso


def test_un_intrusione_suona_anche_a_silenzioso_attivo():
    """Se il silenzioso potesse spegnere un allarme, sarebbe un modo per
    spegnere l'allarme dimenticandosene."""
    allarme = dominio.Avviso(dominio.SICUREZZA, "Intrusione", priorita=dominio.URGENTE)
    zitto = dominio.Preferenze("alessio", silenzioso=True)

    canali = dominio.canali_per(allarme, zitto)

    assert dominio.PUSH in canali


def test_un_avviso_energetico_no():
    """Il rovescio: senza, «tutto passa il silenzioso» supererebbe il test
    di sopra."""
    consumo = dominio.Avviso(dominio.ENERGIA, "Consumi alti", priorita=dominio.INFORMATIVA)
    zitto = dominio.Preferenze("alessio", silenzioso=True)

    assert dominio.PUSH not in dominio.canali_per(consumo, zitto)


def test_il_silenzioso_lascia_passare_la_dashboard():
    """Chi sta guardando lo schermo non viene disturbato da cio' che c'e'
    gia' scritto sopra."""
    consumo = dominio.Avviso(dominio.ENERGIA, "Consumi alti")
    zitto = dominio.Preferenze("alessio", silenzioso=True)

    assert dominio.canali_per(consumo, zitto) == [dominio.WEB]


def test_silenziare_una_categoria_non_le_silenzia_tutte():
    """Il criterio di accettazione della scheda."""
    preferenze = dominio.Preferenze("alessio", categorie_silenziate=frozenset({dominio.ENERGIA}))

    energia = dominio.Avviso(dominio.ENERGIA, "Consumi alti")
    promemoria = dominio.Avviso(dominio.PROMEMORIA, "Comprare il pane")

    assert dominio.canali_per(energia, preferenze) == []
    assert dominio.PUSH in dominio.canali_per(promemoria, preferenze)


def test_la_sicurezza_non_si_puo_silenziare_nemmeno_volendo():
    preferenze = dominio.Preferenze("alessio", categorie_silenziate=frozenset({dominio.SICUREZZA}))
    allarme = dominio.Avviso(dominio.SICUREZZA, "Intrusione", priorita=dominio.URGENTE)

    assert dominio.canali_per(allarme, preferenze) != []


def test_un_intrusione_non_viene_annunciata_ad_alta_voce():
    """Avviserebbe chi e' in casa — eventualmente il ladro — e non chi e'
    fuori."""
    allarme = dominio.Avviso(dominio.SICUREZZA, "Intrusione", priorita=dominio.URGENTE)
    tutto_acceso = dominio.Preferenze("alessio")

    assert dominio.VOCE not in dominio.canali_per(allarme, tutto_acceso)


def test_un_promemoria_urgente_invece_si():
    """Il rovescio: la voce non e' spenta in generale, e' spenta per la
    sicurezza."""
    promemoria = dominio.Avviso(dominio.PROMEMORIA, "Le medicine", priorita=dominio.URGENTE)

    assert dominio.VOCE in dominio.canali_per(promemoria, dominio.Preferenze("alessio"))


def test_un_canale_spento_non_viene_usato():
    preferenze = dominio.Preferenze("alessio", canali={dominio.PUSH: False})
    avviso = dominio.Avviso(dominio.PROMEMORIA, "Qualcosa")

    assert dominio.PUSH not in dominio.canali_per(avviso, preferenze)


def test_senza_preferenze_si_avvisa_lo_stesso():
    """Una casa che di serie non avvisa sembra rotta: chi non vuole essere
    disturbato lo dice."""
    urgente = dominio.Avviso(dominio.SICUREZZA, "Intrusione", priorita=dominio.URGENTE)

    assert dominio.PUSH in dominio.canali_per(urgente, None)


def test_l_ordine_dei_canali_e_dal_meno_invadente():
    """Prima la dashboard, che costa niente; per ultima la voce, l'unica che
    disturba anche chi non era il destinatario."""
    avviso = dominio.Avviso(dominio.PROMEMORIA, "Qualcosa", priorita=dominio.URGENTE)

    canali = dominio.canali_per(avviso, dominio.Preferenze("alessio"))

    assert canali == [dominio.WEB, dominio.PUSH, dominio.VOCE]


# ============================================ dall'evento all'avviso


def test_l_intrusione_diventa_un_avviso_urgente():
    """Il difetto che questa funzione ripara: prima questo evento non
    diventava niente."""
    evento = Evento(tipo=CASA_INTRUSIONE, dati={"persone_in_casa": ["alessio"]})

    avviso = servizio_modulo._avviso_da(evento)

    assert avviso is not None
    assert avviso.categoria == dominio.SICUREZZA
    assert avviso.priorita == dominio.URGENTE
    assert "alessio" in avviso.testo


def test_l_intrusione_a_casa_vuota_lo_dice():
    evento = Evento(tipo=CASA_INTRUSIONE, dati={"persone_in_casa": []})

    avviso = servizio_modulo._avviso_da(evento)

    assert "non risulta nessuno" in avviso.testo


@pytest.mark.parametrize(
    "tipo,dati,categoria",
    [
        (PROMEMORIA_SCADUTO, {"testo": "comprare il pane"}, dominio.PROMEMORIA),
        (TIMER_SCADUTO, {"etichetta": "pasta"}, dominio.TIMER),
    ],
)
def test_gli_altri_eventi_diventano_avvisi(tipo, dati, categoria):
    avviso = servizio_modulo._avviso_da(Evento(tipo=tipo, dati=dati))

    assert avviso is not None
    assert avviso.categoria == categoria


def test_non_tutto_cio_che_succede_diventa_una_notifica():
    """Una casa che notifica ogni cambio di stato di ogni lampadina viene
    silenziata il primo giorno, e poi non avvisa piu' nemmeno di cio' che
    conta."""
    assert servizio_modulo._avviso_da(Evento(tipo="ha.stato_cambiato", dati={})) is None


def test_ogni_avviso_porta_dove_serve():
    """Una notifica che apre la schermata iniziale costringe a cercare cio'
    che e' appena successo."""
    intrusione = servizio_modulo._avviso_da(Evento(tipo=CASA_INTRUSIONE, dati={}))
    promemoria = servizio_modulo._avviso_da(Evento(tipo=PROMEMORIA_SCADUTO, dati={"testo": "x"}))

    assert intrusione.destinazione != "/"
    assert promemoria.destinazione != intrusione.destinazione


# ============================================ l'invio vero


async def test_un_avviso_raggiunge_il_telefono(con_telefono, push_finto):
    inviati, _ = push_finto

    esito = await con_telefono.avvisa(
        dominio.Avviso(dominio.PROMEMORIA, "Promemoria", "comprare il pane"), utente="alessio"
    )

    assert esito["inviate"] >= 1
    assert len(inviati) == 1
    assert inviati[0][0] == ENDPOINT
    assert inviati[0][1]["testo"] == "comprare il pane"


async def test_senza_telefoni_registrati_non_si_manda_niente(push_finto):
    inviati, _ = push_finto
    servizio = ServizioNotifiche()

    await servizio.avvisa(dominio.Avviso(dominio.PROMEMORIA, "Qualcosa"), utente="alessio")

    assert inviati == []


async def test_l_intrusione_arriva_al_telefono(con_telefono, push_finto):
    """Il punto di tutta la issue."""
    inviati, _ = push_finto

    await con_telefono._su_evento(Evento(tipo=CASA_INTRUSIONE, dati={"persone_in_casa": []}))

    assert len(inviati) == 1
    assert inviati[0][1]["priorita"] == dominio.URGENTE


async def test_una_categoria_silenziata_non_parte(con_telefono, push_finto):
    inviati, _ = push_finto
    con_telefono.imposta("alessio", "categoria.promemoria", False)

    await con_telefono.avvisa(dominio.Avviso(dominio.PROMEMORIA, "Qualcosa"), utente="alessio")

    assert inviati == []


async def test_ma_l_allarme_parte_lo_stesso(con_telefono, push_finto):
    inviati, _ = push_finto
    con_telefono.imposta("alessio", "silenzioso", True)

    await con_telefono.avvisa(
        dominio.Avviso(dominio.SICUREZZA, "Intrusione", priorita=dominio.URGENTE), utente="alessio"
    )

    assert len(inviati) == 1


# ============================================ le sottoscrizioni morte


async def test_una_sottoscrizione_revocata_viene_tolta(con_telefono, push_finto):
    """410 e' il servizio push che dice «questo indirizzo non esiste piu'»."""
    _, esito = push_finto
    esito["riuscito"], esito["stato"] = False, 410

    await con_telefono.avvisa(dominio.Avviso(dominio.PROMEMORIA, "Qualcosa"), utente="alessio")

    assert depositi.sottoscrizioni_push.per_utente("alessio") == []


async def test_un_problema_di_rete_non_fa_perdere_il_telefono(con_telefono, push_finto):
    """Togliere una sottoscrizione per un timeout vorrebbe dire smettere di
    avvisare qualcuno senza dirglielo."""
    _, esito = push_finto
    esito["riuscito"], esito["stato"] = False, None

    await con_telefono.avvisa(dominio.Avviso(dominio.PROMEMORIA, "Qualcosa"), utente="alessio")

    rimaste = depositi.sottoscrizioni_push.per_utente("alessio")
    assert len(rimaste) == 1
    assert rimaste[0]["fallimenti"] == 1


async def test_ma_dopo_molti_fallimenti_si_molla(con_telefono, push_finto):
    """Un endpoint che non risponde da giorni non e' un problema di rete."""
    from shinra.infra.push.mittente import FALLIMENTI_MASSIMI

    _, esito = push_finto
    esito["riuscito"], esito["stato"] = False, None

    for _ in range(FALLIMENTI_MASSIMI):
        await con_telefono.avvisa(dominio.Avviso(dominio.PROMEMORIA, "Qualcosa"), utente="alessio")

    assert depositi.sottoscrizioni_push.per_utente("alessio") == []


async def test_un_invio_riuscito_azzera_i_fallimenti(con_telefono, push_finto):
    _, esito = push_finto
    esito["riuscito"], esito["stato"] = False, None
    await con_telefono.avvisa(dominio.Avviso(dominio.PROMEMORIA, "x"), utente="alessio")

    esito["riuscito"], esito["stato"] = True, 201
    await con_telefono.avvisa(dominio.Avviso(dominio.PROMEMORIA, "x"), utente="alessio")

    assert depositi.sottoscrizioni_push.per_utente("alessio")[0]["fallimenti"] == 0


# ============================================ registrare un telefono


def test_lo_stesso_telefono_non_si_registra_due_volte():
    """Senza questo, ogni ricaricamento della pagina lascerebbe una riga in
    piu' e ogni notifica arriverebbe moltiplicata."""
    servizio = ServizioNotifiche()

    servizio.registra_dispositivo("alessio", ENDPOINT, "a", "b", "Telefono")
    servizio.registra_dispositivo("alessio", ENDPOINT, "a2", "b2", "Telefono")

    righe = depositi.sottoscrizioni_push.per_utente("alessio")
    assert len(righe) == 1
    assert righe[0]["p256dh"] == "a2"


def test_due_telefoni_diversi_sono_due_righe():
    servizio = ServizioNotifiche()

    servizio.registra_dispositivo("alessio", ENDPOINT, "a", "b", "Telefono")
    servizio.registra_dispositivo("alessio", ENDPOINT + "-2", "c", "d", "Tablet")

    assert len(depositi.sottoscrizioni_push.per_utente("alessio")) == 2


def test_dimenticare_un_telefono():
    servizio = ServizioNotifiche()
    servizio.registra_dispositivo("alessio", ENDPOINT, "a", "b")

    assert servizio.dimentica_dispositivo(ENDPOINT) is True
    assert depositi.sottoscrizioni_push.per_utente("alessio") == []


# ============================================ le preferenze


def test_le_preferenze_si_leggono_dalle_righe():
    righe = [
        {"user_id": "alessio", "chiave": "silenzioso", "valore": True},
        {"user_id": "alessio", "chiave": "canale.push", "valore": False},
        {"user_id": "alessio", "chiave": "categoria.energia", "valore": False},
        {"user_id": "giulia", "chiave": "silenzioso", "valore": False},
    ]

    preferenze = dominio.preferenze_da_righe("alessio", righe)

    assert preferenze.silenzioso is True
    assert preferenze.vuole_canale(dominio.PUSH) is False
    assert preferenze.vuole_categoria(dominio.ENERGIA) is False
    assert preferenze.vuole_categoria(dominio.PROMEMORIA) is True


def test_le_preferenze_di_un_altro_non_contano():
    righe = [{"user_id": "giulia", "chiave": "silenzioso", "valore": True}]

    assert dominio.preferenze_da_righe("alessio", righe).silenzioso is False


def test_impostare_una_preferenza_due_volte_non_fa_due_righe():
    servizio = ServizioNotifiche()

    servizio.imposta("alessio", "silenzioso", True)
    servizio.imposta("alessio", "silenzioso", False)

    righe = depositi.preferenze_notifiche.per_utente("alessio")
    assert len(righe) == 1
    assert righe[0]["valore"] is False


# ============================================ le chiavi VAPID


def test_le_chiavi_generate_sono_una_p256_valida():
    """Il browser rifiuta silenziosamente una chiave malformata, e le
    notifiche «non funzionano» senza un errore da leggere."""
    import base64

    from shinra.infra.push import mittente

    chiavi = mittente.genera_chiavi()

    pubblica = base64.urlsafe_b64decode(chiavi.pubblica + "=" * (-len(chiavi.pubblica) % 4))
    privata = base64.urlsafe_b64decode(chiavi.privata + "=" * (-len(chiavi.privata) % 4))

    assert len(pubblica) == 65 and pubblica[0] == 0x04
    assert len(privata) == 32
    assert chiavi.valide


def test_le_chiavi_si_salvano_e_si_rileggono(tmp_path, monkeypatch):
    from shinra.infra.push import mittente

    monkeypatch.setattr(mittente, "percorso_chiavi", lambda: tmp_path / "vapid.json")

    prime = mittente.chiavi()
    seconde = mittente.chiavi()

    assert prime is not None
    assert prime.pubblica == seconde.pubblica


def test_le_chiavi_non_si_rigenerano_da_sole(tmp_path, monkeypatch):
    """Cambiare le chiavi invalida in silenzio tutte le sottoscrizioni: una
    casa che smette di avvisare senza dirlo e' peggio di una che non ha mai
    avvisato."""
    from shinra.infra.push import mittente

    percorso = tmp_path / "vapid.json"
    monkeypatch.setattr(mittente, "percorso_chiavi", lambda: percorso)

    prime = mittente.chiavi()
    salvato = percorso.read_text(encoding="utf-8")

    mittente.chiavi()

    assert percorso.read_text(encoding="utf-8") == salvato
    assert mittente.carica_chiavi().pubblica == prime.pubblica


def test_chiavi_illeggibili_non_fanno_esplodere_niente(tmp_path, monkeypatch):
    from shinra.infra.push import mittente

    percorso = tmp_path / "vapid.json"
    percorso.write_text("questo non e' json", encoding="utf-8")
    monkeypatch.setattr(mittente, "percorso_chiavi", lambda: percorso)

    assert mittente.carica_chiavi() is None


@pytest.mark.parametrize("stato,definitivo", [(404, True), (410, True), (500, False), (None, False)])
def test_solo_alcuni_stati_sono_definitivi(stato, definitivo):
    from shinra.infra.push.mittente import Esito

    assert Esito(False, stato=stato).definitivo is definitivo


def test_non_si_puo_togliere_il_telefono_di_un_altro():
    """Senza il controllo di proprieta', chiunque avesse una sessione
    potrebbe togliere il telefono di un altro conoscendone l'endpoint, e
    l'altro smetterebbe di ricevere gli allarmi senza accorgersene.

    L'ha fatto emergere il test che pretende un permesso su ogni rotta che
    cambia qualcosa: qui il permesso non serve — le notifiche sono personali
    — ma il controllo di proprieta' si'.
    """
    servizio = ServizioNotifiche()
    servizio.registra_dispositivo("giulia", ENDPOINT, "a", "b", "Telefono di Giulia")

    assert servizio.dimentica_dispositivo(ENDPOINT, utente="alessio") is False
    assert len(depositi.sottoscrizioni_push.per_utente("giulia")) == 1

    assert servizio.dimentica_dispositivo(ENDPOINT, utente="giulia") is True
    assert depositi.sottoscrizioni_push.per_utente("giulia") == []


def test_i_dispositivi_elencati_non_mostrano_le_chiavi():
    """Le chiavi servono a cifrare, non a farsi guardare."""
    servizio = ServizioNotifiche()
    servizio.registra_dispositivo("alessio", ENDPOINT, "chiave-segreta", "auth-segreta")

    elencati = servizio.dispositivi_di("alessio")

    assert len(elencati) == 1
    testo = repr(elencati)
    assert "chiave-segreta" not in testo
    assert "auth-segreta" not in testo
    assert ENDPOINT not in testo
