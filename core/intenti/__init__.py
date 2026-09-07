"""Il registro degli intenti.

Importare questo pacchetto registra tutti gli intenti noti: l'agente non li
conosce uno per uno, scorre il registro in ordine di priorita'. Aggiungerne
uno vuol dire scrivere una classe e registrarla — `process_user_input` non
si tocca.
"""

from core.intenti import casa, informazioni, promemoria  # noqa: F401  (registrano gli intenti)
from core.intenti.base import Intento, Richiesta, Risposta, azzera, instrada, intenti, registra

__all__ = ["Intento", "Richiesta", "Risposta", "azzera", "instrada", "intenti", "registra"]
