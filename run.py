"""Avvio del servizio.

Resta come alias del comando `shinra` installato dal pacchetto: il servizio
in produzione parte da qui (`deploy/shinra.service`) e cambiare il modo di
avviarlo insieme al resto avrebbe reso lo spostamento della issue #16 un
aggiornamento che non riparte.
"""

from shinra.avvio import principale

if __name__ == "__main__":
    principale()
