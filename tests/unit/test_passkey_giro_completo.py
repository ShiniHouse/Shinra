"""Il giro completo, con un autenticatore finto ma vero.

Gli altri test delle passkey sostituiscono la crittografia con dei finti:
provano le decisioni — chi entra, chi no, chi puo' revocare cosa — e sono
quelli che contano di piu'. Ma lasciano scoperto proprio il pezzo dove un
errore non si vede: **una firma sbagliata accettata lo stesso** non fa
fallire niente, non scrive niente nel log, e sembra funzionare benissimo.

Qui c'e' un autenticatore costruito a mano: una chiave EC P-256, i byte
dell'`authenticatorData` composti a mano, la firma vera. Fa quello che fa un
telefono, e produce risposte che `py_webauthn` deve accettare — e, cambiando
un byte, rifiutare.

Riferimento: issue #48.
"""

from __future__ import annotations

import base64
import hashlib
import json

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from shinra.infra import passkey as cripto

RP_ID = "casa.example"
ORIGINE = "https://casa.example"

# I bit dell'`authenticatorData`. UP: qualcuno era presente. UV: e' stato
# verificato — impronta, volto, o il codice del dispositivo. AT: la risposta
# porta con se' una credenziale nuova. BE/BS: la credenziale e' sincronizzabile
# ed e' sincronizzata, cioe' e' una passkey moderna e non una chiavetta.
UP, UV, BE, BS, AT = 0x01, 0x04, 0x08, 0x10, 0x40


def _b64(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).decode().rstrip("=")


class AutenticatoreFinto:
    """Il minimo che un telefono fa, per poterlo verificare davvero."""

    def __init__(self, credenziale_id: bytes = b"credenziale-di-prova-0001") -> None:
        self.chiave = ec.generate_private_key(ec.SECP256R1())
        self.credenziale_id = credenziale_id
        self.contatore = 0

    # ------------------------------------------------------------ pezzi

    def _cose_pubblica(self) -> bytes:
        numeri = self.chiave.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # curva: P-256
                -2: numeri.x.to_bytes(32, "big"),
                -3: numeri.y.to_bytes(32, "big"),
            }
        )

    def _dati_autenticatore(self, flag: int, con_credenziale: bool) -> bytes:
        dati = hashlib.sha256(RP_ID.encode()).digest()
        dati += bytes([flag])
        dati += self.contatore.to_bytes(4, "big")
        if con_credenziale:
            pubblica = self._cose_pubblica()
            dati += b"\x00" * 16  # aaguid
            dati += len(self.credenziale_id).to_bytes(2, "big")
            dati += self.credenziale_id
            dati += pubblica
        return dati

    @staticmethod
    def _dati_cliente(tipo: str, sfida: bytes, origine: str = ORIGINE) -> bytes:
        return json.dumps(
            {"type": tipo, "challenge": _b64(sfida), "origin": origine, "crossOrigin": False}
        ).encode()

    # ------------------------------------------------------- le risposte

    def registra(self, sfida: bytes, origine: str = ORIGINE, verificato: bool = True) -> dict:
        flag = UP | AT | BE | BS | (UV if verificato else 0)
        oggetto = cbor2.dumps(
            {"fmt": "none", "attStmt": {}, "authData": self._dati_autenticatore(flag, True)}
        )
        return {
            "id": _b64(self.credenziale_id),
            "rawId": _b64(self.credenziale_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64(self._dati_cliente("webauthn.create", sfida, origine)),
                "attestationObject": _b64(oggetto),
            },
        }

    def firma(self, sfida: bytes, origine: str = ORIGINE, avanza: int = 1) -> dict:
        self.contatore += avanza
        dati = self._dati_autenticatore(UP | UV | BE | BS, False)
        cliente = self._dati_cliente("webauthn.get", sfida, origine)
        firma = self.chiave.sign(dati + hashlib.sha256(cliente).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": _b64(self.credenziale_id),
            "rawId": _b64(self.credenziale_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64(cliente),
                "authenticatorData": _b64(dati),
                "signature": _b64(firma),
                "userHandle": _b64(b"alessio"),
            },
        }


@pytest.fixture
def autenticatore():
    return AutenticatoreFinto()


# ----------------------------------------------------------- le opzioni


def test_le_opzioni_di_registrazione_chiedono_cio_che_serve():
    """`residentKey` richiesta e `userVerification` richiesta insieme sono
    cio' che realizza il criterio della scheda: si accede con il volto o
    l'impronta, senza digitare nulla e senza dire prima chi si e'."""
    opzioni = cripto.opzioni_registrazione(
        rp_id=RP_ID,
        nome_casa="Shinra",
        utente_id="alessio",
        nome_utente="Alessio",
        sfida=cripto.nuova_sfida(),
    )

    assert opzioni["rp"]["id"] == RP_ID
    assert opzioni["authenticatorSelection"]["residentKey"] == "required"
    assert opzioni["authenticatorSelection"]["userVerification"] == "required"


def test_le_opzioni_di_accesso_non_elencano_le_credenziali():
    """Un elenco direbbe a chiunque apra la pagina chi vive in questa casa e
    quanti dispositivi ha."""
    opzioni = cripto.opzioni_accesso(RP_ID, cripto.nuova_sfida())

    assert opzioni["rpId"] == RP_ID
    assert not opzioni.get("allowCredentials")
    assert opzioni["userVerification"] == "required"


def test_le_credenziali_gia_registrate_vengono_escluse():
    """Senza, lo stesso telefono registra due passkey per la stessa persona e
    l'elenco si riempie di righe indistinguibili."""
    gia = _b64(b"credenziale-vecchia")

    opzioni = cripto.opzioni_registrazione(
        rp_id=RP_ID,
        nome_casa="Shinra",
        utente_id="alessio",
        nome_utente="Alessio",
        sfida=cripto.nuova_sfida(),
        gia_registrate=[gia],
    )

    assert [c["id"] for c in opzioni["excludeCredentials"]] == [gia]


# -------------------------------------------------------- la registrazione


def test_una_registrazione_vera_viene_accettata(autenticatore):
    sfida = cripto.nuova_sfida()

    registrata = cripto.verifica_registrazione(
        credenziale=autenticatore.registra(sfida), sfida=sfida, rp_id=RP_ID, origine=ORIGINE
    )

    assert registrata.credenziale_id == _b64(autenticatore.credenziale_id)
    assert registrata.chiave_pubblica
    assert registrata.tipo_dispositivo == "multi_device"


def test_una_registrazione_con_la_sfida_sbagliata_viene_rifiutata(autenticatore):
    """Il punto di tutta la faccenda: senza questo controllo una risposta
    intercettata si potrebbe rigiocare."""
    credenziale = autenticatore.registra(cripto.nuova_sfida())

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_registrazione(
            credenziale=credenziale, sfida=cripto.nuova_sfida(), rp_id=RP_ID, origine=ORIGINE
        )


def test_una_registrazione_da_un_altra_origine_viene_rifiutata(autenticatore):
    sfida = cripto.nuova_sfida()
    credenziale = autenticatore.registra(sfida, origine="https://sito-ostile.example")

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_registrazione(credenziale=credenziale, sfida=sfida, rp_id=RP_ID, origine=ORIGINE)


def test_una_registrazione_senza_verifica_dell_utente_viene_rifiutata(autenticatore):
    """«C'era qualcuno» non basta: dev'essere stato riconosciuto. Altrimenti
    chi trova il telefono sbloccato entra in casa."""
    sfida = cripto.nuova_sfida()
    credenziale = autenticatore.registra(sfida, verificato=False)

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_registrazione(credenziale=credenziale, sfida=sfida, rp_id=RP_ID, origine=ORIGINE)


# ------------------------------------------------------------- l'accesso


def _iscrivi(autenticatore) -> str:
    sfida = cripto.nuova_sfida()
    return cripto.verifica_registrazione(
        credenziale=autenticatore.registra(sfida), sfida=sfida, rp_id=RP_ID, origine=ORIGINE
    ).chiave_pubblica


def test_un_accesso_vero_viene_accettato(autenticatore):
    pubblica = _iscrivi(autenticatore)
    sfida = cripto.nuova_sfida()

    verificata = cripto.verifica_accesso(
        credenziale=autenticatore.firma(sfida),
        sfida=sfida,
        rp_id=RP_ID,
        origine=ORIGINE,
        chiave_pubblica=pubblica,
        contatore=0,
    )

    assert verificata.credenziale_id == _b64(autenticatore.credenziale_id)
    assert verificata.contatore == 1


def test_una_firma_manomessa_viene_rifiutata(autenticatore):
    """Il test che giustifica tutto questo file: se la verifica della firma
    non funzionasse, nient'altro se ne accorgerebbe."""
    pubblica = _iscrivi(autenticatore)
    sfida = cripto.nuova_sfida()
    credenziale = autenticatore.firma(sfida)

    grezza = bytearray(cripto._da_b64(credenziale["response"]["signature"]))
    grezza[-1] ^= 0x01
    credenziale["response"]["signature"] = _b64(bytes(grezza))

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_accesso(
            credenziale=credenziale,
            sfida=sfida,
            rp_id=RP_ID,
            origine=ORIGINE,
            chiave_pubblica=pubblica,
            contatore=0,
        )


def test_la_firma_di_un_altra_chiave_viene_rifiutata(autenticatore):
    """Due telefoni diversi, la stessa credenziale dichiarata: la firma non
    torna, ed e' l'unica cosa che conta."""
    pubblica = _iscrivi(autenticatore)
    intruso = AutenticatoreFinto(credenziale_id=autenticatore.credenziale_id)
    sfida = cripto.nuova_sfida()

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_accesso(
            credenziale=intruso.firma(sfida),
            sfida=sfida,
            rp_id=RP_ID,
            origine=ORIGINE,
            chiave_pubblica=pubblica,
            contatore=0,
        )


def test_un_accesso_con_la_sfida_di_prima_viene_rifiutato(autenticatore):
    pubblica = _iscrivi(autenticatore)
    vecchia = cripto.nuova_sfida()
    credenziale = autenticatore.firma(vecchia)

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_accesso(
            credenziale=credenziale,
            sfida=cripto.nuova_sfida(),
            rp_id=RP_ID,
            origine=ORIGINE,
            chiave_pubblica=pubblica,
            contatore=0,
        )


def test_un_accesso_da_un_altra_origine_viene_rifiutato(autenticatore):
    """E' cio' che rende una passkey immune al phishing: il sito ostile puo'
    copiare la pagina, non l'origine."""
    pubblica = _iscrivi(autenticatore)
    sfida = cripto.nuova_sfida()

    with pytest.raises(cripto.VerificaFallita):
        cripto.verifica_accesso(
            credenziale=autenticatore.firma(sfida, origine="https://sito-ostile.example"),
            sfida=sfida,
            rp_id=RP_ID,
            origine=ORIGINE,
            chiave_pubblica=pubblica,
            contatore=0,
        )


def test_il_contatore_torna_come_lo_manda_l_autenticatore(autenticatore):
    """Il servizio ci costruisce sopra il controllo sulle copie: se qui
    tornasse sempre zero, quel controllo non troverebbe mai niente."""
    pubblica = _iscrivi(autenticatore)
    sfida = cripto.nuova_sfida()

    verificata = cripto.verifica_accesso(
        credenziale=autenticatore.firma(sfida, avanza=9),
        sfida=sfida,
        rp_id=RP_ID,
        origine=ORIGINE,
        chiave_pubblica=pubblica,
        contatore=0,
    )

    assert verificata.contatore == 9
