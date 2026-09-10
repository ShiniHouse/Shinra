"""Registrare e riconoscere una passkey.

`domain/passkey.py` decide *se si puo'* e *su quale dominio*;
`infra/passkey.py` fa la crittografia. Qui c'e' il resto: le sfide in attesa,
cosa si salva, e chi si lascia entrare.

**Le sfide stanno in memoria.** Sono monouso e durano due minuti: scriverle
sul disco vorrebbe dire conservare per sempre righe che valgono per pochi
secondi, e dopo un riavvio del server un accesso a meta' va comunque
ricominciato. Perderle costa un tentativo; tenerle costa una tabella da
ripulire.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from shinra.domain import passkey as dominio
from shinra.infra import passkey as cripto

logger = logging.getLogger("Shinra.Passkey")

# Quante sfide si tengono contemporaneamente. Un tetto perche' un endpoint
# pubblico che alloca memoria a ogni chiamata e' un modo educato di far
# finire la RAM a un server di casa.
SFIDE_MASSIME = 200


class NonSiPuo(Exception):
    """Le passkey non sono disponibili qui, e il messaggio dice perche'."""


class AccessoRifiutato(Exception):
    """La credenziale non e' stata accettata."""


@dataclass
class _Sfida:
    valore: bytes
    scade: float
    utente: Optional[str] = None


class ServizioPasskey:
    def __init__(self) -> None:
        self._sfide: dict[str, _Sfida] = {}

    # ------------------------------------------------------- il contesto

    def contesto(self, schema: str, host: str) -> dominio.Contesto:
        """Se qui le passkey si possono usare, e con quale dominio."""
        from shinra.config.settings import settings

        # Il percorso per intero e non `getattr`: la guardia della issue #26
        # cerca `security.passkey_rp_id` scritto cosi', e un'opzione che
        # nessuno sembra leggere e' un'opzione che prima o poi qualcuno
        # cancella.
        return dominio.leggi_contesto(
            schema,
            host,
            rp_id_configurato=settings.security.passkey_rp_id,
            origine_configurata=settings.security.passkey_origine,
            libreria_presente=cripto.disponibile(),
        )

    def stato(self, schema: str, host: str) -> dict[str, Any]:
        """Cosa dire all'interfaccia prima di mostrare un pulsante.

        Un pulsante che fallisce con un errore del browser e' peggio di un
        pulsante assente: chi lo preme conclude che il server e' rotto.
        """
        contesto = self.contesto(schema, host)
        return {
            "disponibile": contesto.disponibile,
            "motivo": contesto.motivo,
            "spiegazione": dominio.spiega(contesto.motivo),
        }

    def _esigi_contesto(self, schema: str, host: str) -> dominio.Contesto:
        contesto = self.contesto(schema, host)
        if not contesto.disponibile:
            raise NonSiPuo(dominio.spiega(contesto.motivo))
        return contesto

    # --------------------------------------------------------- le sfide

    def _pulisci(self) -> None:
        adesso = time.monotonic()
        scadute = [c for c, s in self._sfide.items() if s.scade < adesso]
        for chiave in scadute:
            self._sfide.pop(chiave, None)

        # Se dopo la pulizia ce ne sono ancora troppe, si buttano le piu'
        # vecchie: qualcuno sta chiamando l'endpoint a raffica, e perdere una
        # sfida costa un tentativo mentre esaurire la memoria costa il server.
        if len(self._sfide) >= SFIDE_MASSIME:
            piu_vecchie = sorted(self._sfide.items(), key=lambda voce: voce[1].scade)
            for chiave, _ in piu_vecchie[: len(self._sfide) - SFIDE_MASSIME + 1]:
                self._sfide.pop(chiave, None)
            logger.warning("Troppe sfide passkey in attesa: le piu' vecchie sono state scartate.")

    def _apri_sfida(self, utente: Optional[str]) -> tuple[str, bytes]:
        """Apre una sfida e restituisce la chiave con cui ritrovarla.

        La chiave e' casuale e viaggia fino al browser invece di essere
        dedotta da chi chiede. Dedurla — dall'indirizzo, o da un'unica casella
        per tutti — vorrebbe dire che due persone che entrano nello stesso
        momento si scavalcano la sfida a vicenda, e che aprire una seconda
        scheda invalida la prima. Non e' un segreto: la sfida stessa arriva al
        browser, che deve firmarla. A proteggere e' la firma, non la chiave.
        """
        self._pulisci()
        chiave = cripto.nuova_sfida().hex()
        valore = cripto.nuova_sfida()
        self._sfide[chiave] = _Sfida(valore, time.monotonic() + dominio.DURATA_SFIDA, utente)
        return chiave, valore

    def _consuma_sfida(self, chiave: str, utente: Optional[str] = None) -> _Sfida:
        """Una sfida vale una volta sola.

        Toglierla prima di verificare e non dopo: se restasse in piedi dopo un
        tentativo fallito, chi ha intercettato la risposta di qualcun altro
        potrebbe rigiocarla finche' non passa.
        """
        sfida = self._sfide.pop(chiave or "", None)
        if sfida is None or sfida.scade < time.monotonic():
            raise AccessoRifiutato("La richiesta e' scaduta. Riprova.")
        if utente is not None and sfida.utente != utente:
            # Una sfida aperta per registrare la passkey di una persona non
            # deve poter chiudere la registrazione di un'altra.
            raise AccessoRifiutato("La richiesta e' scaduta. Riprova.")
        return sfida

    def dimentica_sfide(self) -> None:
        """Solo per i test."""
        self._sfide.clear()

    # --------------------------------------------------- la registrazione

    def inizia_registrazione(self, utente: Any, schema: str, host: str) -> dict[str, Any]:
        from shinra.infra.db import depositi

        contesto = self._esigi_contesto(schema, host)
        gia = [r["id"] for r in depositi.passkey.per_utente(utente.id)]
        chiave, sfida = self._apri_sfida(utente.id)

        opzioni = cripto.opzioni_registrazione(
            rp_id=contesto.rp_id,
            nome_casa=self._nome_casa(),
            utente_id=utente.id,
            nome_utente=utente.name,
            sfida=sfida,
            gia_registrate=gia,
        )
        return {"sfida_id": chiave, "opzioni": opzioni}

    def concludi_registrazione(
        self,
        utente: Any,
        credenziale: dict[str, Any],
        nome: str,
        sfida_id: str,
        schema: str,
        host: str,
    ) -> dict[str, Any]:
        from shinra.infra.db import depositi

        contesto = self._esigi_contesto(schema, host)
        sfida = self._consuma_sfida(sfida_id, utente.id)

        try:
            registrata = cripto.verifica_registrazione(
                credenziale=credenziale,
                sfida=sfida.valore,
                rp_id=contesto.rp_id,
                origine=contesto.origine,
            )
        except cripto.VerificaFallita as errore:
            raise AccessoRifiutato(str(errore)) from errore

        usati = frozenset(r["nome"] for r in depositi.passkey.per_utente(utente.id))
        riga = depositi.passkey.salva(
            {
                "id": registrata.credenziale_id,
                "user_id": utente.id,
                "nome": dominio.nome_pulito(nome, usati),
                "chiave_pubblica": registrata.chiave_pubblica,
                "contatore": registrata.contatore,
                "rp_id": contesto.rp_id,
                "tipo_dispositivo": registrata.tipo_dispositivo,
            }
        )
        logger.info("Passkey registrata per %s: %s", utente.name, riga["nome"])
        return riga

    # -------------------------------------------------------- l'accesso

    def inizia_accesso(self, schema: str, host: str) -> dict[str, Any]:
        contesto = self._esigi_contesto(schema, host)
        chiave, sfida = self._apri_sfida(None)
        return {"sfida_id": chiave, "opzioni": cripto.opzioni_accesso(contesto.rp_id, sfida)}

    def concludi_accesso(self, credenziale: dict[str, Any], sfida_id: str, schema: str, host: str) -> Any:
        """Verifica la firma e restituisce il profilo di chi e' entrato.

        Aprire la sessione non e' compito di questo servizio: le sessioni
        stanno in `api/sicurezza`, e un servizio non puo' salire fino a li'.
        """
        from shinra.infra.db import depositi
        from shinra.services.user_manager import user_manager

        contesto = self._esigi_contesto(schema, host)
        sfida = self._consuma_sfida(sfida_id)

        identificativo = cripto.identificativo_dalla_risposta(credenziale)
        riga = depositi.passkey.per_id(identificativo) if identificativo else None
        if riga is None:
            # Stesso messaggio del caso «firma sbagliata»: distinguerli
            # direbbe a chi prova quali credenziali esistono.
            logger.warning("Passkey sconosciuta presentata all'accesso.")
            raise AccessoRifiutato("Questa passkey non e' riconosciuta.")

        try:
            verificata = cripto.verifica_accesso(
                credenziale=credenziale,
                sfida=sfida.valore,
                rp_id=contesto.rp_id,
                origine=contesto.origine,
                chiave_pubblica=riga["chiave_pubblica"],
                contatore=int(riga["contatore"] or 0),
            )
        except cripto.VerificaFallita as errore:
            raise AccessoRifiutato("Questa passkey non e' riconosciuta.") from errore

        if dominio.contatore_regredito(int(riga["contatore"] or 0), verificata.contatore):
            # Una chiave che sta in due posti non e' piu' una prova di chi
            # sei. Si rifiuta e si lascia la riga: cancellarla in silenzio
            # toglierebbe alla persona l'unico segnale che qualcosa non va.
            logger.error(
                "Contatore regredito per la passkey %s (%s -> %s): possibile copia.",
                riga["nome"],
                riga["contatore"],
                verificata.contatore,
            )
            raise AccessoRifiutato(
                "Questa passkey sembra essere stata copiata: non la accetto. "
                "Entra con il PIN e revocala dalle impostazioni."
            )

        profilo = user_manager.get_user_by_id(riga["user_id"])
        if profilo is None:
            # Il profilo e' stato cancellato mentre la credenziale restava.
            depositi.passkey.cancella(riga["id"])
            logger.warning("Passkey di un profilo inesistente (%s): rimossa.", riga["user_id"])
            raise AccessoRifiutato("Questa passkey non e' riconosciuta.")

        depositi.passkey.segna_uso(riga["id"], verificata.contatore)
        return profilo

    # ------------------------------------------------- dalle impostazioni

    def mie(self, utente: Any) -> list[dict[str, Any]]:
        """Le passkey di una persona, senza la chiave pubblica.

        Non e' un segreto — con quella non si apre niente — ma e' rumore in
        un elenco che serve a scegliere quale revocare.
        """
        from shinra.infra.db import depositi

        return [
            {c: v for c, v in riga.items() if c != "chiave_pubblica"}
            for riga in depositi.passkey.per_utente(utente.id)
        ]

    def revoca(self, utente: Any, identificativo: str) -> bool:
        """Toglie una passkey, ma solo se e' tua.

        Senza il controllo di proprieta', chiunque sia entrato in casa
        potrebbe togliere il telefono di un altro conoscendone
        l'identificativo — che compare nel proprio elenco solo per se', ma
        non e' un segreto.
        """
        from shinra.infra.db import depositi

        riga = depositi.passkey.per_id(identificativo)
        if riga is None or riga["user_id"] != utente.id:
            return False
        return depositi.passkey.cancella(identificativo)

    # ---------------------------------------------------------- di servizio

    @staticmethod
    def _nome_casa() -> str:
        from shinra.config.settings import settings

        return (getattr(settings.assistant, "name", "") or "Shinra").strip() or "Shinra"


servizio_passkey = ServizioPasskey()
