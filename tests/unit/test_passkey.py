"""Le passkey: dove si possono usare, e chi entra.

Il PIN e' cio' che si puo' digitare, e cio' che si puo' guardare mentre
qualcuno lo digita. Una passkey no: la chiave privata resta nel telefono e si
sblocca con impronta o volto. Ma una passkey vale per **un dominio solo**, e
in una casa il dominio spesso non c'e' — `http://192.168.1.50:8000` non e' un
nome e non e' HTTPS. Meta' di questi test verificano che in quel caso Shinra
lo dica, invece di mostrare un pulsante che fallisce con un errore del
browser.

L'altra meta' verifica cosa succede a chi entra: che una firma sbagliata non
apra, che una credenziale copiata venga fermata, e che nessuno possa revocare
il telefono di un altro.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

import pytest

from shinra.domain import passkey as dominio
from shinra.infra.db import depositi
from shinra.services import passkey as servizio_modulo
from shinra.services.passkey import AccessoRifiutato, NonSiPuo, servizio_passkey

# ============================================================ il dominio


@pytest.mark.parametrize(
    "schema,host,atteso",
    [
        ("https", "casa.example", "casa.example"),
        ("https", "casa.example:8443", "casa.example"),
        ("https", "CASA.Example", "casa.example"),
        ("http", "localhost:8000", "localhost"),
        ("http", "127.0.0.1:8000", None),
    ],
)
def test_il_dominio_si_ricava_dalla_richiesta(schema, host, atteso):
    contesto = dominio.leggi_contesto(schema, host)

    if atteso is None:
        assert not contesto.disponibile
    else:
        assert contesto.disponibile
        assert contesto.rp_id == atteso


def test_a_un_indirizzo_numerico_le_passkey_non_ci_sono():
    """Il caso normale in una casa, non l'eccezione: l'`rp_id` dev'essere un
    nome di dominio, e `192.168.1.50` non lo e'."""
    contesto = dominio.leggi_contesto("http", "192.168.1.50:8000")

    assert not contesto.disponibile
    assert contesto.motivo == dominio.INDIRIZZO_NUMERICO
    assert "nome di dominio" in dominio.spiega(contesto.motivo)


def test_anche_un_indirizzo_numerico_in_https_non_basta():
    """HTTPS su un indirizzo IP resta un indirizzo IP."""
    contesto = dominio.leggi_contesto("https", "192.168.1.50")

    assert contesto.motivo == dominio.INDIRIZZO_NUMERICO


def test_senza_https_le_passkey_non_ci_sono():
    contesto = dominio.leggi_contesto("http", "casa.example")

    assert not contesto.disponibile
    assert contesto.motivo == dominio.SENZA_HTTPS
    assert "PIN" in dominio.spiega(contesto.motivo)


def test_localhost_in_chiaro_e_un_contesto_sicuro():
    """E' la stessa regola dei service worker: i browser considerano
    `localhost` sicuro anche senza certificato."""
    assert dominio.leggi_contesto("http", "localhost:8000").disponibile


def test_senza_la_libreria_le_passkey_non_ci_sono():
    """Dipendenza facoltativa: se manca, si entra con il PIN. Il criterio
    della scheda e' che chi non le vuole non perda niente."""
    contesto = dominio.leggi_contesto("https", "casa.example", libreria_presente=False)

    assert contesto.motivo == dominio.LIBRERIA_ASSENTE
    assert "PIN" in dominio.spiega(contesto.motivo)


def test_il_dominio_configurato_vince_su_quello_della_richiesta():
    """Serve a chi raggiunge la casa a piu' nomi: senza un valore fisso, una
    passkey registrata da fuori non funziona da dentro, e l'errore si
    presenta come «la passkey non e' riconosciuta»."""
    contesto = dominio.leggi_contesto("https", "shinra.local", rp_id_configurato="casa.example")

    assert contesto.rp_id == "casa.example"


def test_l_origine_configurata_vince_su_quella_della_richiesta():
    contesto = dominio.leggi_contesto("https", "interno:8000", origine_configurata="https://casa.example")

    assert contesto.origine == "https://casa.example"


def test_l_origine_ricavata_tiene_la_porta():
    """`https://casa.example:8443` e `https://casa.example` sono origini
    diverse per il browser, e la firma non verrebbe accettata."""
    contesto = dominio.leggi_contesto("https", "casa.example:8443")

    assert contesto.origine == "https://casa.example:8443"


# ------------------------------------------------------- il contatore


def test_un_contatore_che_va_avanti_va_bene():
    assert not dominio.contatore_regredito(5, 6)


@pytest.mark.parametrize("salvato,nuovo", [(5, 5), (5, 4), (5, 0)])
def test_un_contatore_che_non_avanza_e_una_copia(salvato, nuovo):
    """Una chiave che sta in due posti non e' piu' una prova di chi sei."""
    assert dominio.contatore_regredito(salvato, nuovo)


def test_zero_contro_zero_non_e_una_copia():
    """Molti autenticatori moderni — comprese le passkey sincronizzate fra i
    dispositivi di una persona — non tengono affatto il contatore e mandano
    sempre zero. Preteso li', il controllo non troverebbe cloni: escluderebbe
    gli utenti normali."""
    assert not dominio.contatore_regredito(0, 0)


# ------------------------------------------------------------- i nomi


def test_un_nome_vuoto_ne_riceve_uno():
    assert dominio.nome_pulito("") == dominio.NOME_PREDEFINITO
    assert dominio.nome_pulito("   ") == dominio.NOME_PREDEFINITO


def test_i_nomi_doppi_si_distinguono():
    """Un elenco di tre «iPhone» non si revoca con fiducia, e chi non e'
    sicuro non revoca."""
    assert dominio.nome_pulito("iPhone", frozenset({"iPhone"})) == "iPhone (2)"
    assert dominio.nome_pulito("iPhone", frozenset({"iPhone", "iPhone (2)"})) == "iPhone (3)"


def test_un_nome_lunghissimo_viene_accorciato():
    lungo = "x" * 500

    assert len(dominio.nome_pulito(lungo)) == dominio.NOME_MASSIMO


# ============================================== il servizio e l'archivio


@pytest.fixture(autouse=True)
def casa_pulita():
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "sonia", "name": "Sonia", "role": "adult"},
        ]
    )
    servizio_passkey.dimentica_sfide()
    yield
    servizio_passkey.dimentica_sfide()


def _registra(utente: str, identificativo: str, nome: str = "Telefono", contatore: int = 0) -> None:
    depositi.passkey.salva(
        {
            "id": identificativo,
            "user_id": utente,
            "nome": nome,
            "chiave_pubblica": "finta",
            "contatore": contatore,
            "rp_id": "casa.example",
            "tipo_dispositivo": "multi_device",
        }
    )


def _profilo(identificativo: str):
    from shinra.services.user_manager import user_manager

    return user_manager.get_user_by_id(identificativo)


def test_dove_non_si_puo_il_servizio_lo_dice_invece_di_provarci():
    stato = servizio_passkey.stato("http", "192.168.1.50:8000")

    assert stato["disponibile"] is False
    assert stato["spiegazione"]


def test_dove_non_si_puo_iniziare_una_registrazione_solleva():
    with pytest.raises(NonSiPuo):
        servizio_passkey.inizia_registrazione(_profilo("alessio"), "http", "192.168.1.50")


def test_una_sfida_vale_una_volta_sola(monkeypatch):
    """Se restasse in piedi dopo essere stata usata, chi ha intercettato la
    risposta di qualcun altro potrebbe rigiocarla.

    La prima scrittura di questo test provava due tentativi **falliti** e
    verificava che fallissero entrambi: passava anche con la sfida lasciata
    in piedi, perche' a farli fallire era la credenziale sconosciuta. Qui il
    primo tentativo riesce, ed e' l'unica forma in cui la domanda «e' stata
    consumata?» ha una risposta.
    """
    _registra("alessio", "cred-1", contatore=0)
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})
    monkeypatch.setattr(
        servizio_modulo.cripto,
        "verifica_accesso",
        lambda **altro: servizio_modulo.cripto.Verificata("cred-1", 1),
    )
    apertura = servizio_passkey.inizia_accesso("https", "casa.example")

    entrato = servizio_passkey.concludi_accesso(
        {"id": "cred-1"}, apertura["sfida_id"], "https", "casa.example"
    )
    assert entrato.id == "alessio"

    with pytest.raises(AccessoRifiutato) as errore:
        servizio_passkey.concludi_accesso({"id": "cred-1"}, apertura["sfida_id"], "https", "casa.example")

    assert "scaduta" in str(errore.value)


def test_una_sfida_inventata_non_vale(monkeypatch):
    with pytest.raises(AccessoRifiutato):
        servizio_passkey.concludi_accesso({"id": "x"}, "sfida-inventata", "https", "casa.example")


def test_due_accessi_insieme_non_si_rubano_la_sfida(monkeypatch):
    """Una casella sola per tutti vorrebbe dire che chi entra per secondo
    invalida la sfida del primo — e che aprire una seconda scheda basta a
    rompere l'accesso."""
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})

    primo = servizio_passkey.inizia_accesso("https", "casa.example")
    secondo = servizio_passkey.inizia_accesso("https", "casa.example")

    assert primo["sfida_id"] != secondo["sfida_id"]
    assert servizio_passkey._sfide[primo["sfida_id"]].valore is not None
    assert servizio_passkey._sfide[secondo["sfida_id"]].valore is not None


def test_una_sfida_di_registrazione_non_chiude_quella_di_un_altro(monkeypatch):
    """La sfida aperta per Alessio non deve registrare una passkey a Sonia.

    Anche questo test, scritto la prima volta, passava per il motivo
    sbagliato: la crittografia non era sostituita, quindi il rifiuto arrivava
    dalla verifica della firma e non dal controllo su chi avesse aperto la
    sfida. Qui la verifica **riesce**, e a fermare resta solo il controllo
    che si vuole provare.
    """
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_registrazione", lambda **altro: {})
    monkeypatch.setattr(
        servizio_modulo.cripto,
        "verifica_registrazione",
        lambda **altro: servizio_modulo.cripto.Registrata("cred-nuova", "pubblica", 0, "multi_device"),
    )
    apertura = servizio_passkey.inizia_registrazione(_profilo("alessio"), "https", "casa.example")

    with pytest.raises(AccessoRifiutato):
        servizio_passkey.concludi_registrazione(
            _profilo("sonia"), {}, "Telefono", apertura["sfida_id"], "https", "casa.example"
        )

    assert depositi.passkey.per_id("cred-nuova") is None, "non deve essere nata nessuna passkey"


def test_la_propria_sfida_di_registrazione_conclude(monkeypatch):
    """L'altra meta': il controllo non deve fermare anche chi ha diritto."""
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_registrazione", lambda **altro: {})
    monkeypatch.setattr(
        servizio_modulo.cripto,
        "verifica_registrazione",
        lambda **altro: servizio_modulo.cripto.Registrata("cred-nuova", "pubblica", 0, "multi_device"),
    )
    apertura = servizio_passkey.inizia_registrazione(_profilo("alessio"), "https", "casa.example")

    riga = servizio_passkey.concludi_registrazione(
        _profilo("alessio"), {}, "iPhone", apertura["sfida_id"], "https", "casa.example"
    )

    assert riga["user_id"] == "alessio"
    assert riga["nome"] == "iPhone"
    assert depositi.passkey.per_id("cred-nuova")["rp_id"] == "casa.example"


def test_una_passkey_sconosciuta_non_entra(monkeypatch):
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})
    apertura = servizio_passkey.inizia_accesso("https", "casa.example")

    with pytest.raises(AccessoRifiutato) as errore:
        servizio_passkey.concludi_accesso({"id": "mai-vista"}, apertura["sfida_id"], "https", "casa.example")

    assert "non e' riconosciuta" in str(errore.value)


def test_una_passkey_copiata_viene_fermata(monkeypatch):
    """Il contatore che non avanza e' l'unico segnale che una credenziale
    esiste in due copie."""
    _registra("alessio", "cred-1", contatore=7)
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})
    monkeypatch.setattr(
        servizio_modulo.cripto,
        "verifica_accesso",
        lambda **altro: servizio_modulo.cripto.Verificata("cred-1", 3),
    )
    apertura = servizio_passkey.inizia_accesso("https", "casa.example")

    with pytest.raises(AccessoRifiutato) as errore:
        servizio_passkey.concludi_accesso({"id": "cred-1"}, apertura["sfida_id"], "https", "casa.example")

    assert "copiata" in str(errore.value)
    # La riga resta: cancellarla in silenzio toglierebbe alla persona
    # l'unico segnale che qualcosa non va.
    assert depositi.passkey.per_id("cred-1") is not None
    assert depositi.passkey.per_id("cred-1")["contatore"] == 7


def test_una_passkey_valida_apre_e_aggiorna_il_contatore(monkeypatch):
    _registra("sonia", "cred-2", contatore=3)
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})
    monkeypatch.setattr(
        servizio_modulo.cripto,
        "verifica_accesso",
        lambda **altro: servizio_modulo.cripto.Verificata("cred-2", 4),
    )
    apertura = servizio_passkey.inizia_accesso("https", "casa.example")

    profilo = servizio_passkey.concludi_accesso(
        {"id": "cred-2"}, apertura["sfida_id"], "https", "casa.example"
    )

    assert profilo.id == "sonia"
    riga = depositi.passkey.per_id("cred-2")
    assert riga["contatore"] == 4
    assert riga["ultimo_uso"] is not None


def test_una_passkey_di_un_profilo_cancellato_non_entra(monkeypatch):
    """Succede cancellando una persona: la credenziale resta e punta al
    vuoto. Entrare con essa vorrebbe dire entrare come nessuno."""
    _registra("fantasma", "cred-3", contatore=1)
    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})
    monkeypatch.setattr(
        servizio_modulo.cripto,
        "verifica_accesso",
        lambda **altro: servizio_modulo.cripto.Verificata("cred-3", 2),
    )
    apertura = servizio_passkey.inizia_accesso("https", "casa.example")

    with pytest.raises(AccessoRifiutato):
        servizio_passkey.concludi_accesso({"id": "cred-3"}, apertura["sfida_id"], "https", "casa.example")

    assert depositi.passkey.per_id("cred-3") is None, "una credenziale orfana va tolta"


def test_una_firma_sbagliata_non_entra(monkeypatch):
    _registra("alessio", "cred-4")

    def rifiuta(**altro):
        raise servizio_modulo.cripto.VerificaFallita("no")

    monkeypatch.setattr(servizio_modulo.cripto, "opzioni_accesso", lambda rp_id, sfida: {})
    monkeypatch.setattr(servizio_modulo.cripto, "verifica_accesso", rifiuta)
    apertura = servizio_passkey.inizia_accesso("https", "casa.example")

    with pytest.raises(AccessoRifiutato):
        servizio_passkey.concludi_accesso({"id": "cred-4"}, apertura["sfida_id"], "https", "casa.example")


# --------------------------------------------------------- la gestione


def test_l_elenco_non_espone_la_chiave_pubblica():
    """Non e' un segreto — con quella non si apre niente — ma e' rumore in un
    elenco che serve a scegliere quale revocare."""
    _registra("alessio", "cred-5")

    elenco = servizio_passkey.mie(_profilo("alessio"))

    assert len(elenco) == 1
    assert "chiave_pubblica" not in elenco[0]
    assert elenco[0]["nome"] == "Telefono"


def test_si_vedono_solo_le_proprie():
    _registra("alessio", "cred-a")
    _registra("sonia", "cred-b")

    assert [r["id"] for r in servizio_passkey.mie(_profilo("sonia"))] == ["cred-b"]


def test_non_si_revoca_la_passkey_di_un_altro():
    """L'identificativo compare nel proprio elenco, ma non e' un segreto: la
    proprieta' va verificata, non presunta."""
    _registra("sonia", "cred-b")

    assert servizio_passkey.revoca(_profilo("alessio"), "cred-b") is False
    assert depositi.passkey.per_id("cred-b") is not None


def test_si_revoca_la_propria():
    _registra("sonia", "cred-b")

    assert servizio_passkey.revoca(_profilo("sonia"), "cred-b") is True
    assert depositi.passkey.per_id("cred-b") is None


def test_revocare_una_che_non_esiste_non_e_un_errore():
    assert servizio_passkey.revoca(_profilo("alessio"), "mai-vista") is False
