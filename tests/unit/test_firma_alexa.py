"""Nessuno comanda la casa da Internet senza la firma di Amazon.

`/api/alexa` e' l'unico endpoint di Shinra raggiungibile dall'esterno, e
prima di questi controlli eseguiva comandi domotici accettando qualunque POST.

I test non simulano la verifica: costruiscono una vera catena di certificati
X.509 e firmano davvero le richieste. Una verifica di firma provata con
finzioni non prova niente — il difetto tipico e' proprio che la funzione
sembra funzionare e non guarda cio' che dovrebbe.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from integrations.alexa import verifica_firma as vf
from integrations.alexa.verifica_firma import FirmaNonValida

SKILL_ID = "amzn1.ask.skill.0000-1111-2222"
URL_VALIDO = "https://s3.amazonaws.com/echo.api/echo-api-cert-1.pem"


# --------------------------------------------------------------- impalcatura


def _chiave() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _certificato(
    chiave: rsa.RSAPrivateKey,
    firmatario: rsa.RSAPrivateKey | None = None,
    nome_soggetto: str = "echo-api.amazon.com",
    nome_emittente: str = "Radice di prova",
    san: str | None = "echo-api.amazon.com",
    da: datetime | None = None,
    a: datetime | None = None,
) -> x509.Certificate:
    adesso = datetime.now(timezone.utc)
    soggetto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome_soggetto)])
    emittente = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome_emittente)])

    builder = (
        x509.CertificateBuilder()
        .subject_name(soggetto)
        .issuer_name(emittente)
        .public_key(chiave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(da or adesso - timedelta(days=1))
        .not_valid_after(a or adesso + timedelta(days=30))
    )
    if san:
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(san)]), critical=False)
    return builder.sign(firmatario or chiave, hashes.SHA256())


@pytest.fixture()
def amazon_finto():
    """Una radice, un certificato foglia firmato da lei, e la sua chiave."""
    radice_chiave = _chiave()
    radice = _certificato(
        radice_chiave, nome_soggetto="Radice di prova", nome_emittente="Radice di prova", san=None
    )
    foglia_chiave = _chiave()
    foglia = _certificato(foglia_chiave, firmatario=radice_chiave)
    pem = foglia.public_bytes(serialization.Encoding.PEM) + radice.public_bytes(serialization.Encoding.PEM)
    return {"foglia": foglia, "chiave": foglia_chiave, "radice": radice, "pem": pem}


def _richiesta(timestamp: datetime | None = None, skill: str = SKILL_ID) -> bytes:
    momento = timestamp or datetime.now(timezone.utc)
    return json.dumps(
        {
            "version": "1.0",
            "session": {"application": {"applicationId": skill}},
            "request": {
                "type": "IntentRequest",
                "timestamp": momento.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "intent": {"name": "TurnOnIntent"},
            },
        }
    ).encode()


def _firma(chiave: rsa.RSAPrivateKey, corpo: bytes) -> str:
    return base64.b64encode(chiave.sign(corpo, padding.PKCS1v15(), hashes.SHA1())).decode()


@pytest.fixture(autouse=True)
def _cache_pulita():
    vf._cache_certificati.clear()
    yield
    vf._cache_certificati.clear()


# ------------------------------------------------------- l'URL della catena


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://s3.amazonaws.com/echo.api/cert.pem",  # non cifrato
        "https://malintenzionato.com/echo.api/cert.pem",  # host di chi attacca
        "https://s3.amazonaws.com/altro/cert.pem",  # percorso sbagliato
        "https://s3.amazonaws.com:8443/echo.api/cert.pem",  # porta anomala
        "https://s3.amazonaws.com/echo.api/../malevolo.pem",  # risalita di percorso
        "https://s3.amazonaws.com.malintenzionato.com/echo.api/c.pem",  # host che somiglia
    ],
)
def test_url_della_catena_non_ammessi(url: str) -> None:
    """E' il controllo da cui dipendono tutti gli altri.

    Senza, chi attacca indica la propria catena, firma con la propria chiave e
    ogni verifica successiva darebbe esito positivo.
    """
    with pytest.raises(FirmaNonValida):
        vf.valida_url_certificato(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://s3.amazonaws.com/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com:443/echo.api/echo-api-cert-7.pem",
        "https://S3.AmazonAWS.com/echo.api/cert.pem",  # host senza distinzione di maiuscole
    ],
)
def test_url_della_catena_ammessi(url: str) -> None:
    assert vf.valida_url_certificato(url) == url


# ------------------------------------------------------------ il certificato


def test_catena_valida(amazon_finto) -> None:
    catena = [amazon_finto["foglia"], amazon_finto["radice"]]
    assert vf.valida_catena(catena) is amazon_finto["foglia"]


def test_certificato_scaduto() -> None:
    chiave = _chiave()
    adesso = datetime.now(timezone.utc)
    scaduto = _certificato(chiave, da=adesso - timedelta(days=60), a=adesso - timedelta(days=1))
    with pytest.raises(FirmaNonValida, match="scaduto"):
        vf.valida_catena([scaduto])


def test_certificato_senza_il_nome_di_amazon() -> None:
    chiave = _chiave()
    estraneo = _certificato(chiave, nome_soggetto="esempio.it", san="esempio.it")
    with pytest.raises(FirmaNonValida, match=re.escape("echo-api.amazon.com")):
        vf.valida_catena([estraneo])


def test_certificato_estraneo_accodato_alla_catena(amazon_finto) -> None:
    """Un certificato che non ha firmato quello prima di lui va rifiutato."""
    altra_radice = _certificato(
        _chiave(), nome_soggetto="Radice di prova", nome_emittente="Radice di prova", san=None
    )
    with pytest.raises(FirmaNonValida):
        vf.valida_catena([amazon_finto["foglia"], altra_radice])


# -------------------------------------------------------------------- firma


def test_firma_corretta(amazon_finto) -> None:
    corpo = _richiesta()
    vf.valida_firma(amazon_finto["foglia"], _firma(amazon_finto["chiave"], corpo), corpo)


def test_firma_di_un_altra_chiave(amazon_finto) -> None:
    corpo = _richiesta()
    with pytest.raises(FirmaNonValida, match="non corrisponde"):
        vf.valida_firma(amazon_finto["foglia"], _firma(_chiave(), corpo), corpo)


def test_corpo_alterato_dopo_la_firma(amazon_finto) -> None:
    """Il caso che conta: intercettare una richiesta legittima e cambiarne il
    contenuto — da «accendi la luce» a «apri la porta»."""
    originale = _richiesta()
    firma = _firma(amazon_finto["chiave"], originale)
    alterato = originale.replace(b"TurnOnIntent", b"UnlockDoorX")
    with pytest.raises(FirmaNonValida, match="non corrisponde"):
        vf.valida_firma(amazon_finto["foglia"], firma, alterato)


@pytest.mark.parametrize("firma", ["", "non-base64!!", base64.b64encode(b"corta").decode()])
def test_firme_malformate(amazon_finto, firma: str) -> None:
    with pytest.raises(FirmaNonValida):
        vf.valida_firma(amazon_finto["foglia"], firma, _richiesta())


# ------------------------------------------------------------------- tempo


def test_timestamp_recente() -> None:
    vf.valida_timestamp(json.loads(_richiesta()))


@pytest.mark.parametrize("scarto", [timedelta(minutes=10), timedelta(minutes=-10), timedelta(days=1)])
def test_timestamp_fuori_tolleranza(scarto: timedelta) -> None:
    """Senza questo controllo una richiesta intercettata resta riutilizzabile
    per sempre: chi la registra puo' rigiocarla mesi dopo."""
    dati = json.loads(_richiesta(timestamp=datetime.now(timezone.utc) + scarto))
    with pytest.raises(FirmaNonValida):
        vf.valida_timestamp(dati)


@pytest.mark.parametrize("dati", [{}, {"request": {}}, {"request": {"timestamp": "ieri"}}])
def test_timestamp_assente_o_illeggibile(dati: dict) -> None:
    with pytest.raises(FirmaNonValida):
        vf.valida_timestamp(dati)


# ------------------------------------------------------------- identita' skill


def test_skill_id_corretto() -> None:
    vf.valida_skill_id(json.loads(_richiesta()), SKILL_ID)


def test_skill_id_di_un_altra_skill() -> None:
    dati = json.loads(_richiesta(skill="amzn1.ask.skill.di-qualcun-altro"))
    with pytest.raises(FirmaNonValida, match="un'altra skill"):
        vf.valida_skill_id(dati, SKILL_ID)


@pytest.mark.parametrize("configurato", [None, "", "   "])
def test_senza_skill_id_configurato_si_rifiuta(configurato) -> None:
    """Un controllo che si spegne da solo quando non e' configurato non e' un
    controllo: senza applicationId atteso, la richiesta va rifiutata."""
    with pytest.raises(FirmaNonValida, match="SHINRA_ALEXA_SKILL_ID"):
        vf.valida_skill_id(json.loads(_richiesta()), configurato)


def test_skill_id_letto_anche_dal_contesto() -> None:
    """Le richieste senza sessione portano l'applicationId dentro `context`."""
    dati = {
        "context": {"System": {"application": {"applicationId": SKILL_ID}}},
        "request": {"type": "IntentRequest"},
    }
    vf.valida_skill_id(dati, SKILL_ID)


# ------------------------------------------------------------ verifica intera


@pytest.mark.asyncio
async def test_verifica_completa_di_una_richiesta_autentica(amazon_finto, monkeypatch) -> None:
    async def catena_finta(url, client=None):
        vf.valida_url_certificato(url)
        return [amazon_finto["foglia"], amazon_finto["radice"]]

    monkeypatch.setattr(vf, "scarica_catena", catena_finta)
    corpo = _richiesta()
    await vf.verifica_richiesta(
        corpo=corpo,
        intestazioni={
            "SignatureCertChainUrl": URL_VALIDO,
            "Signature": _firma(amazon_finto["chiave"], corpo),
        },
        dati=json.loads(corpo),
        skill_id_atteso=SKILL_ID,
    )


@pytest.mark.asyncio
async def test_la_catena_non_viene_scaricata_se_i_controlli_a_costo_zero_falliscono(monkeypatch) -> None:
    """Ordine dei controlli: una raffica di richieste contraffatte non deve
    trasformarsi in una raffica di richieste verso Amazon."""
    scaricamenti = []

    async def conta(url, client=None):
        scaricamenti.append(url)
        return []

    monkeypatch.setattr(vf, "scarica_catena", conta)
    with pytest.raises(FirmaNonValida):
        await vf.verifica_richiesta(
            corpo=b"{}",
            intestazioni={"SignatureCertChainUrl": URL_VALIDO, "Signature": "x"},
            dati=json.loads(_richiesta(skill="skill-sbagliata")),
            skill_id_atteso=SKILL_ID,
        )
    assert scaricamenti == []
