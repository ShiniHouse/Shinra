"""La conoscenza di casa, recuperata invece che riversata.

Prima ogni fatto abilitato finiva nel prompt di ogni richiesta. Con la
modalita' apprendimento funzionante la conoscenza cresce in fretta, e il
contesto cresceva con lei: prima si paga in latenza, poi si satura la
finestra e i fatti piu' vecchi vengono troncati **in silenzio**. La casa
dimentica senza dirlo, ed e' il difetto peggiore possibile per una funzione
che si chiama «memoria».

Come funziona, in ordine di importanza:

1. **Se i fatti sono pochi si mandano tutti**, come si e' sempre fatto. Il
   problema esiste a duecento fatti, non a venti, e un recupero imperfetto
   dove non serviva farebbe perdere risposte che prima funzionavano.
2. Sopra la soglia si recupera per similarita' **e** per testo.
3. Se gli embedding non ci sono — Ollama spento, modello non installato —
   resta la strada testuale. La casa risponde peggio, non smette di sapere.

L'indice si tiene aggiornato da solo confrontando l'impronta del testo: un
fatto modificato ha un'impronta diversa da quella salvata, e il vettore viene
rifatto senza che nessuno debba ricordarsi di chiamare qualcosa.

Riferimento: issue #32.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from shinra.domain import recupero as dominio

logger = logging.getLogger("Shinra.Conoscenza")

# Quanti fatti indicizzare per volta. Ollama calcola un lotto in una
# chiamata sola, e lotti troppo grandi lo tengono occupato mentre qualcuno
# sta parlando alla casa.
LOTTO = 32


class ServizioConoscenza:
    def __init__(self) -> None:
        self.ultimo_recupero: list[Mapping[str, Any]] = []
        self.semantico_disponibile: Optional[bool] = None

    # --------------------------------------------------------- l'indice

    def _fatti_attivi(self) -> list[dict[str, Any]]:
        from shinra.infra.db import depositi

        return [f for f in depositi.fatti.elenco() if f.get("enabled", True)]

    async def aggiorna_indice(self, forza: bool = False) -> dict[str, int]:
        """Calcola i vettori mancanti o invecchiati.

        `forza` rifa' tutto: serve quando si cambia modello di embedding,
        perche' vettori di modelli diversi vivono in spazi diversi e
        confrontarli produce numeri che sembrano punteggi e non lo sono.
        """
        from shinra.infra.db import depositi
        from shinra.infra.llm import embedding

        fatti = self._fatti_attivi()
        salvati = depositi.embedding.tutti()
        modello_attuale = embedding.modello()

        da_fare = []
        for fatto in fatti:
            identificativo = str(fatto["id"])
            testo = str(fatto.get("text") or "")
            gia = salvati.get(identificativo)
            impronta = dominio.impronta(testo)

            if (
                forza
                or gia is None
                or str(gia.get("impronta")) != impronta
                or str(gia.get("modello")) != modello_attuale
            ):
                da_fare.append((identificativo, testo, impronta))

        tolti = depositi.embedding.dimentica_orfani({str(f["id"]) for f in fatti})

        if not da_fare:
            return {"calcolati": 0, "orfani_tolti": tolti, "totali": len(fatti)}

        calcolati = 0
        for inizio in range(0, len(da_fare), LOTTO):
            lotto = da_fare[inizio : inizio + LOTTO]
            vettori = await embedding.calcola([t for _, t, _ in lotto])
            # `strict=True` perche' `calcola` promette una lista lunga
            # quanto quella ricevuta: se un giorno non fosse piu' vero, e'
            # meglio un errore qui che dei vettori attribuiti al fatto
            # sbagliato — quelli non darebbero errore, darebbero risposte
            # sbagliate.
            for (identificativo, _, impronta), vettore in zip(lotto, vettori, strict=True):
                if not vettore:
                    continue
                depositi.embedding.salva(identificativo, vettore, modello_attuale, impronta)
                calcolati += 1

        self.semantico_disponibile = calcolati > 0 or depositi.embedding.conta() > 0
        if calcolati:
            logger.info("Conoscenza: %d embedding calcolati su %d fatti.", calcolati, len(fatti))
        elif da_fare:
            logger.info(
                "Conoscenza: nessun embedding calcolato (modello «%s» non disponibile). "
                "Il recupero resta testuale.",
                modello_attuale,
            )

        return {"calcolati": calcolati, "orfani_tolti": tolti, "totali": len(fatti)}

    # ------------------------------------------------------ il recupero

    def _con_vettori(self) -> list[dominio.Fatto]:
        from shinra.infra.db import depositi

        vettori = depositi.embedding.tutti()
        fuori = []
        for fatto in self._fatti_attivi():
            identificativo = str(fatto["id"])
            salvato = vettori.get(identificativo) or {}
            fuori.append(
                dominio.Fatto(
                    identificativo=identificativo,
                    testo=str(fatto.get("text") or ""),
                    categoria=str(fatto.get("category") or "generale"),
                    vettore=list(salvato.get("vettore") or []) or None,
                )
            )
        return fuori

    async def per_la_domanda(self, domanda: str) -> str:
        """La conoscenza da mettere nel prompt per questa domanda.

        E' il sostituto di `get_enabled_knowledge_summary()`, e produce la
        stessa forma: cambiare forma insieme al meccanismo vorrebbe dire non
        sapere quale delle due cose ha cambiato le risposte.
        """
        from shinra.infra.llm import embedding

        fatti = self._con_vettori()
        self.ultimo_recupero = []

        if not fatti:
            return "Nessuna informazione personalizzata registrata."

        if not dominio.serve_recuperare(len(fatti)):
            # Pochi fatti: si manda tutto, come prima. Nessuna chiamata di
            # embedding, nessuna latenza aggiunta, nessun rischio di
            # lasciare fuori quello giusto.
            return dominio.tutti_come_prompt(fatti)

        vettore_domanda: Optional[Sequence[float]] = None
        if any(f.vettore for f in fatti):
            calcolati = await embedding.calcola([domanda])
            vettore_domanda = calcolati[0] if calcolati else None

        trovati = dominio.cerca(domanda, fatti, vettore_domanda)
        self.ultimo_recupero = dominio.spiega(trovati)

        if not trovati:
            # Niente di pertinente non e' un errore: la domanda non
            # riguardava la casa. Mandare i primi cinque «meno lontani»
            # riempirebbe il prompt di rumore.
            return ""

        return dominio.come_prompt(trovati)

    def fatti_usati(self) -> list[Mapping[str, Any]]:
        """Quali fatti hanno contribuito all'ultima risposta.

        Quando l'assistente risponde una cosa strana, la prima domanda e'
        «da dove l'ha presa».
        """
        return list(self.ultimo_recupero)

    # ------------------------------------------------------------ stato

    async def stato(self) -> dict[str, Any]:
        from shinra.infra.db import depositi
        from shinra.infra.llm import embedding

        fatti = self._fatti_attivi()
        con_vettore = depositi.embedding.conta()

        return {
            "fatti": len(fatti),
            "con_embedding": con_vettore,
            "modello": embedding.modello(),
            "soglia_recupero": dominio.SOGLIA_RECUPERO,
            "massimo_nel_prompt": dominio.MASSIMO_FATTI,
            # Sotto la soglia il recupero non serve, e dirlo evita la
            # domanda «perche' non sta recuperando».
            "recupero_attivo": dominio.serve_recuperare(len(fatti)),
            "semantico": con_vettore > 0,
        }


servizio_conoscenza = ServizioConoscenza()
