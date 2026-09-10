"""Da voce a testo, e la domanda che viene prima: dove finisce l'audio.

Il riconoscimento vocale della dashboard usava la Web Speech API, che manda
l'audio ai server del produttore del browser. Il modello girava in casa, e
ogni parola detta usciva verso Google — mentre il README scriveva «Zero Cloud
per i Dati Privati».

Il test piu' importante di questo file e'
`test_un_motore_sconosciuto_non_fa_ripiegare_sul_browser`: fra i due modi di
sbagliare — «non funziona» e «funziona ma manda tutto fuori» — il secondo e'
peggiore perche' non si vede, e una configurazione scritta male non deve
poterci portare.

Il secondo per importanza e' quello sulle allucinazioni: Whisper, sul
silenzio, produce i titoli di coda dei sottotitoli su cui e' stato addestrato.
Mandarli all'agente come comando significa che un microfono aperto per sbaglio
fa partire una richiesta che nessuno ha fatto.

Riferimento: issue #31.
"""

from __future__ import annotations

import pytest

from shinra.domain import trascrizione as dominio
from shinra.services import trascrizione as servizio_modulo
from shinra.services.trascrizione import AudioRifiutato, NonSiPuo, servizio_trascrizione

# ============================================================ il dominio


def test_per_difetto_si_resta_in_casa():
    stato = dominio.scegli_motore("", libreria_presente=True)

    assert stato.motore == dominio.LOCALE
    assert stato.in_casa
    assert stato.pronto


def test_un_motore_sconosciuto_non_fa_ripiegare_sul_browser():
    """Fra i due modi di sbagliare, «funziona ma manda tutto a Google» e'
    peggiore di «non funziona», perche' non si vede."""
    stato = dominio.scegli_motore("bruwser", libreria_presente=True)

    assert stato.motore == dominio.LOCALE


def test_il_browser_si_sceglie_scrivendolo():
    stato = dominio.scegli_motore("browser", libreria_presente=True)

    assert stato.motore == dominio.BROWSER
    assert not stato.in_casa
    assert stato.motivo == dominio.SCELTO_IL_BROWSER


def test_senza_la_libreria_il_motore_locale_non_e_pronto():
    """E non ripiega: il microfono non funziona e lo dice."""
    stato = dominio.scegli_motore("locale", libreria_presente=False)

    assert stato.motore == dominio.LOCALE
    assert not stato.pronto
    assert stato.motivo == dominio.LIBRERIA_ASSENTE


def test_scegliere_il_browser_vale_anche_senza_la_libreria():
    """Chi ha scelto il browser non ha bisogno di niente installato: e' il
    browser a trascrivere."""
    stato = dominio.scegli_motore("browser", libreria_presente=False)

    assert stato.motore == dominio.BROWSER
    assert stato.pronto


@pytest.mark.parametrize(
    "motivo", [dominio.LIBRERIA_ASSENTE, dominio.MODELLO_NON_CARICATO, dominio.SCELTO_IL_BROWSER]
)
def test_ogni_motivo_ha_una_spiegazione(motivo):
    assert dominio.spiega(motivo)


def test_la_spiegazione_della_libreria_assente_dice_come_installarla():
    assert "faster-whisper" in dominio.spiega(dominio.LIBRERIA_ASSENTE)


def test_la_spiegazione_del_browser_dice_che_l_audio_esce_di_casa():
    detto = dominio.spiega(dominio.SCELTO_IL_BROWSER)

    assert "esce di casa" in detto


# ------------------------------------------------------------- i formati


@pytest.mark.parametrize(
    "tipo",
    ["audio/webm", "audio/webm;codecs=opus", "audio/ogg; codecs=opus", "AUDIO/WAV", "audio/mp4"],
)
def test_i_formati_del_browser_si_accettano(tipo):
    """`MediaRecorder` manda `audio/webm;codecs=opus`: confrontare la stringa
    intera con un elenco di tipi puliti rifiuterebbe ogni registrazione fatta
    da Chrome."""
    assert dominio.formato_accettabile(tipo)


@pytest.mark.parametrize("tipo", ["", None, "video/mp4", "application/octet-stream", "text/plain"])
def test_cio_che_non_e_audio_si_rifiuta(tipo):
    assert not dominio.formato_accettabile(tipo)


def test_c_e_un_tetto_alla_dimensione():
    """Un endpoint che accetta caricamenti senza tetto e' un modo educato di
    riempire il disco di un server di casa."""
    assert dominio.troppo_grande(dominio.DIMENSIONE_MASSIMA + 1)
    assert not dominio.troppo_grande(dominio.DIMENSIONE_MASSIMA)


# -------------------------------------------------------- le allucinazioni


@pytest.mark.parametrize(
    "inventato",
    [
        "Sottotitoli e revisione a cura di QTSS",
        "sottotitoli e revisione a cura di qtss",
        "Sottotitoli creati dalla comunità Amara.org",
        "Grazie per aver guardato il video!",
        "Iscriviti al canale.",
        "   ",
        "",
    ],
)
def test_i_titoli_di_coda_sul_silenzio_si_buttano(inventato):
    """Non e' un caso di scuola: Whisper e' stato addestrato anche su
    sottotitoli, e sul silenzio produce i loro titoli di coda. Passarli
    all'agente vuol dire che un microfono aperto per sbaglio fa partire una
    richiesta che nessuno ha fatto."""
    assert dominio.pulisci(inventato) == ""


@pytest.mark.parametrize(
    "detto",
    [
        "accendi la luce del salotto",
        "che tempo fa domani",
        "sì",
        "no",
        "metti un timer di cinque minuti",
    ],
)
def test_un_comando_vero_non_viene_buttato(detto):
    """La meta' che conta di piu': un filtro troppo largo toglie comandi veri,
    e chi parla non capisce perche' la casa non risponde."""
    assert dominio.pulisci(detto) == detto


def test_lo_spazio_in_testa_di_whisper_sparisce():
    assert dominio.pulisci("  accendi la luce ") == "accendi la luce"


def test_i_segmenti_si_riuniscono_con_uno_spazio_solo():
    assert dominio.pulisci(" accendi   la\n luce ") == "accendi la luce"


def test_una_lettera_sola_non_e_un_comando():
    assert dominio.pulisci("a") == ""


# ------------------------------------------------------------- i modelli


@pytest.mark.parametrize("nome", ["base", "TINY", " small "])
def test_i_modelli_noti_si_accettano(nome):
    assert dominio.modello_valido(nome) == nome.strip().lower()


@pytest.mark.parametrize("nome", ["bas", "", "gigante", None])
def test_un_modello_sconosciuto_ripiega_sul_predefinito(nome):
    """Chi ha scritto `bas` invece di `base` si merita un avviso, non una casa
    che non ascolta."""
    assert dominio.modello_valido(nome) == dominio.MODELLO_PREDEFINITO


# ============================================================ il servizio


@pytest.fixture
def con_libreria(monkeypatch):
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    return monkeypatch


def _audio(byte: int = 1024) -> bytes:
    return b"\x00" * byte


def test_l_interfaccia_riceve_tutto_cio_che_le_serve(con_libreria):
    stato = servizio_trascrizione.per_l_interfaccia()

    assert stato["in_casa"] is True
    assert stato["pronto"] is True
    assert stato["modello"] in dominio.MODELLI
    assert stato["megabyte_massimi"] == dominio.MEGABYTE_MASSIMI


def test_senza_la_libreria_l_interfaccia_lo_dice(monkeypatch):
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: False)

    stato = servizio_trascrizione.per_l_interfaccia()

    assert stato["pronto"] is False
    assert "faster-whisper" in stato["spiegazione"]


def test_senza_la_libreria_trascrivere_solleva_invece_di_ripiegare(monkeypatch):
    """Il cuore della issue: non esiste una strada che mandi l'audio fuori
    senza che qualcuno l'abbia scritto in configurazione.

    Il messaggio conta quanto il rifiuto. La prima scrittura di questo test
    verificava solo che sollevasse, e passava anche togliendo il controllo:
    a sollevare era il modello che non si caricava, con un messaggio che
    parlava d'altro. Chi legge «il modello non si e' caricato» aspetta; chi
    legge «installa faster-whisper» installa.
    """
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: False)

    with pytest.raises(NonSiPuo) as errore:
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert "faster-whisper" in str(errore.value)


def test_con_il_browser_scelto_il_server_non_finge_di_trascrivere(monkeypatch):
    """Anche con la libreria installata: la configurazione dice che a
    trascrivere e' il browser, e il server non ha niente da restituire.

    Con la libreria assente questo test passerebbe comunque, per il motivo
    sbagliato — ed e' come era scritto la prima volta.
    """
    from shinra.config.settings import settings

    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(settings.voce, "motore", "browser")

    with pytest.raises(NonSiPuo) as errore:
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert "esce di casa" in str(errore.value)


def test_un_audio_troppo_grande_viene_rifiutato(con_libreria):
    with pytest.raises(AudioRifiutato) as errore:
        servizio_trascrizione.trascrivi(_audio(dominio.DIMENSIONE_MASSIMA + 1), "audio/webm")

    assert str(dominio.MEGABYTE_MASSIMI) in str(errore.value)


def test_un_formato_non_gestito_viene_rifiutato(con_libreria):
    with pytest.raises(AudioRifiutato):
        servizio_trascrizione.trascrivi(_audio(), "video/mp4")


def test_un_audio_vuoto_viene_rifiutato(con_libreria):
    with pytest.raises(AudioRifiutato):
        servizio_trascrizione.trascrivi(b"", "audio/webm")


def test_una_trascrizione_riuscita_torna_pulita(con_libreria, monkeypatch):
    monkeypatch.setattr(
        servizio_modulo.whisper, "trascrivi", lambda audio, modello, lingua: "  accendi la luce "
    )

    assert servizio_trascrizione.trascrivi(_audio(), "audio/webm;codecs=opus") == "accendi la luce"


def test_un_titolo_di_coda_torna_come_niente(con_libreria, monkeypatch):
    monkeypatch.setattr(
        servizio_modulo.whisper,
        "trascrivi",
        lambda audio, modello, lingua: "Sottotitoli e revisione a cura di QTSS",
    )

    assert servizio_trascrizione.trascrivi(_audio(), "audio/webm") == ""


def test_un_modello_che_non_si_carica_non_diventa_un_guasto(con_libreria, monkeypatch):
    def esplode(audio, modello, lingua):
        raise RuntimeError("pesi non trovati")

    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", esplode)

    with pytest.raises(NonSiPuo) as errore:
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert "modello" in str(errore.value).lower()


def test_il_modello_si_legge_dalla_configurazione(con_libreria, monkeypatch):
    from shinra.config.settings import settings

    visti = {}

    def finto(audio, modello, lingua):
        visti["modello"] = modello
        visti["lingua"] = lingua
        return "ciao"

    monkeypatch.setattr(settings.voce, "modello", "small")
    monkeypatch.setattr(settings.voce, "lingua", "it")
    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", finto)

    servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert visti == {"modello": "small", "lingua": "it"}
