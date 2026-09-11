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


@pytest.fixture
def con_modello(con_libreria):
    """La libreria c'e' **e** i pesi sono gia' in memoria.

    Sono due condizioni diverse, e il difetto del 524 sta esattamente nello
    scarto fra le due: la libreria c'era dal primo avvio, i pesi no, e
    scaricarli dentro la richiesta la teneva aperta oltre ogni timeout.
    """
    con_libreria.setattr(servizio_modulo.whisper, "caricato", lambda nome: True)
    return con_libreria


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


def test_i_pesi_gia_scaricati_si_aprono_senza_toccare_la_rete():
    """Il difetto che ha tenuto fermo il microfono per venticinque minuti.

    `WhisperModel`, per difetto, contatta huggingface.co anche quando il
    modello e' gia' in cache: controlla se ce n'e' uno nuovo. Se quella
    chiamata non torna — rete filtrata, DNS muto, il servizio dall'altra
    parte che tace — il caricamento resta appeso, con i pesi sul disco a
    mezzo metro di distanza. In casa: 142 MB scaricati, zero processi al
    lavoro, zero errori, zero CPU, e il microfono fermo.

    Un hub domotico che ha i pesi non deve dipendere da internet per usarli.
    """
    aperture: list[bool] = []

    class ModuloFinto:
        @staticmethod
        def WhisperModel(nome, **opzioni):
            aperture.append(bool(opzioni.get("local_files_only")))
            return "modello"

    assert servizio_modulo.whisper._apri(ModuloFinto, "base") == "modello"
    assert aperture == [True], "la prima apertura e' andata a cercare in rete"


def test_se_i_pesi_non_ci_sono_ancora_si_scaricano():
    """La rete resta la seconda strada, non sparisce: la prima volta, e
    quando qualcuno cambia modello in configurazione, i pesi vanno presi."""
    aperture: list[bool] = []

    class ModuloFinto:
        @staticmethod
        def WhisperModel(nome, **opzioni):
            solo_dal_disco = bool(opzioni.get("local_files_only"))
            aperture.append(solo_dal_disco)
            if solo_dal_disco:
                raise OSError("non c'e' niente in cache")
            return "modello"

    assert servizio_modulo.whisper._apri(ModuloFinto, "base") == "modello"
    assert aperture == [True, False], "senza cache non si e' ripiegato sul download"


def test_senza_la_libreria_non_si_prepara_niente(monkeypatch):
    """Non c'e' niente da caricare, e un filo che parte per scoprirlo e' un
    filo che muore con un'eccezione nel log a ogni avvio."""
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: False)

    assert servizio_modulo.whisper.prepara("base") is False
    assert servizio_modulo.whisper.in_preparazione() is False


def test_con_i_pesi_non_ancora_in_memoria_non_si_trascrive(con_libreria, monkeypatch):
    """Il difetto del 524.

    Whisper carica i pesi al primo uso, e la prima volta li scarica: possono
    volerci minuti. Finche' quel caricamento avveniva dentro la richiesta, la
    richiesta restava aperta per tutto il tempo, e qualunque cosa stia davanti
    al server la tagliava prima — Cloudflare a cento secondi.

    Il rifiuto deve mettere in moto il caricamento, altrimenti non arrivera'
    mai: sarebbe un microfono che dice sempre «sto preparando» e non prepara
    niente.
    """
    avviati = []
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "prepara", lambda nome: avviati.append(nome))

    def non_si_deve_arrivare_qui(audio, modello, lingua):
        raise AssertionError("il modello e' stato fatto girare dentro la richiesta")

    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", non_si_deve_arrivare_qui)

    with pytest.raises(NonSiPuo) as errore:
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert "preparando" in str(errore.value)
    assert avviati, "il rifiuto non mette in moto niente: il modello non arrivera' mai"


def test_un_attesa_lunga_dice_da_quanto_dura(con_libreria, monkeypatch):
    """«Riprova fra un minuto — succede una volta sola», al dodicesimo
    minuto, e' di nuovo una bugia.

    Quanto manchi non si puo' sapere. Da quanto si aspetta si', e basta a
    distinguere un'attesa normale da una che non finira': un caricamento
    fermo da un quarto d'ora assomiglia a uno appena partito, se nessuno
    guarda l'orologio.
    """
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "perche_non_e_pronto", lambda: "")
    monkeypatch.setattr(servizio_modulo.whisper, "da_quanto_prepara", lambda: 12 * 60.0)

    messaggio = servizio_trascrizione.perche_il_modello_non_e_pronto()

    assert "12 minuti" in messaggio
    assert "una volta sola" not in messaggio, "continua a farla sembrare una cosa di un minuto"


def test_un_attesa_appena_cominciata_resta_rassicurante(con_libreria, monkeypatch):
    """Nei primi minuti l'attesa **e'** normale, e dirlo e' corretto: la
    guardia di sopra non deve trasformare ogni avvio in un allarme."""
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "perche_non_e_pronto", lambda: "")
    monkeypatch.setattr(servizio_modulo.whisper, "da_quanto_prepara", lambda: 8.0)

    messaggio = servizio_trascrizione.perche_il_modello_non_e_pronto()

    assert messaggio == dominio.spiega(dominio.MODELLO_IN_PREPARAZIONE)


def test_un_caricamento_fallito_non_si_racconta_come_un_attesa(con_libreria, monkeypatch):
    """La bugia che si ripete identica.

    «Sto preparando il modello: riprova fra un minuto, succede una volta
    sola» e' vero finche' il caricamento sta andando. Se il filo e' gia'
    morto — la rete, il disco pieno, i pesi che non arrivano — la stessa
    frase esce a ogni pressione del microfono e tiene qualcuno ad aspettare
    una cosa che non arrivera' mai. E' successo in casa: cinque minuti di
    «succede una volta sola» mentre non stava succedendo niente.

    Il motivo vero, anche brutto, vale piu' di una rassicurazione.
    """
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "perche_non_e_pronto", lambda: "No space left on device")
    monkeypatch.setattr(servizio_modulo.whisper, "prepara", lambda nome: False)

    with pytest.raises(NonSiPuo) as errore:
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert "No space left on device" in str(errore.value)
    assert "una volta sola" not in str(errore.value), "continua a dire che basta aspettare"


def test_il_motivo_si_legge_prima_di_riprovare(con_libreria, monkeypatch):
    """Rimettere in moto la preparazione azzera il guasto precedente.

    Se il messaggio si componesse dopo, direbbe sempre «sto preparando»:
    il tentativo nuovo avrebbe gia' cancellato il motivo di quello vecchio,
    e il difetto sarebbe tornato identico passando da un'altra porta.
    """
    ordine: list[str] = []

    def perche():
        ordine.append("letto")
        return "pesi non scaricati"

    def prepara(nome):
        ordine.append("riavviato")
        return True

    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "perche_non_e_pronto", perche)
    monkeypatch.setattr(servizio_modulo.whisper, "prepara", prepara)

    with pytest.raises(NonSiPuo):
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    assert ordine == ["letto", "riavviato"]


def test_l_interfaccia_porta_il_motivo_a_chi_preme_il_microfono(con_libreria, monkeypatch):
    """Il messaggio si scrive nel server, non nella pagina: una frase fissa
    nel JavaScript non puo' distinguere un'attesa da un guasto."""
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "perche_non_e_pronto", lambda: "connessione rifiutata")

    stato = servizio_trascrizione.per_l_interfaccia()

    assert "connessione rifiutata" in stato["spiegazione_modello"]


def test_l_interfaccia_distingue_installato_da_caricato(con_libreria, monkeypatch):
    """«C'e' la libreria» e «i pesi sono in memoria» sono due cose diverse, e
    la dashboard deve poterle distinguere per non far parlare qualcuno dentro
    un'attesa di minuti."""
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)

    stato = servizio_trascrizione.per_l_interfaccia()

    assert stato["pronto"] is True
    assert stato["modello_caricato"] is False


def test_col_browser_scelto_non_si_prepara_nessun_modello(monkeypatch):
    """Caricare in memoria un modello che nessuno usera' e' mezzo gigabyte
    buttato su un server di casa."""
    from shinra.config.settings import settings

    chiamate = []
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "prepara", lambda nome: chiamate.append(nome))
    monkeypatch.setattr(settings.voce, "motore", "browser")

    assert servizio_trascrizione.prepara() is False
    assert chiamate == []


def test_una_trascrizione_riuscita_torna_pulita(con_modello, monkeypatch):
    monkeypatch.setattr(
        servizio_modulo.whisper, "trascrivi", lambda audio, modello, lingua: "  accendi la luce "
    )

    assert servizio_trascrizione.trascrivi(_audio(), "audio/webm;codecs=opus") == "accendi la luce"


def test_un_titolo_di_coda_torna_come_niente(con_modello, monkeypatch):
    monkeypatch.setattr(
        servizio_modulo.whisper,
        "trascrivi",
        lambda audio, modello, lingua: "Sottotitoli e revisione a cura di QTSS",
    )

    assert servizio_trascrizione.trascrivi(_audio(), "audio/webm") == ""


def test_un_modello_che_non_si_carica_non_diventa_un_guasto(con_modello, monkeypatch):
    def esplode(audio, modello, lingua):
        raise RuntimeError("pesi non trovati")

    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", esplode)

    with pytest.raises(NonSiPuo) as errore:
        servizio_trascrizione.trascrivi(_audio(), "audio/webm")

    # «non si e' caricato», non «lo sto caricando»: sono due messaggi
    # diversi e portano a due comportamenti diversi — guardare il log
    # oppure aspettare. Cercare la sola parola «modello» li confonde, ed e'
    # cosi' che questo test e' rimasto verde per il motivo sbagliato quando
    # e' comparsa la preparazione in sottofondo.
    assert "non si e' caricato" in str(errore.value)


def test_il_modello_si_legge_dalla_configurazione(con_modello, monkeypatch):
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
