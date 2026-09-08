"""Shinra: l'assistente di casa.

Il numero di versione sta in `pyproject.toml` e basta. `__version__` lo
rilegge dai metadati del pacchetto installato invece di ripeterlo qui:
due numeri scritti a mano divergono, e il giorno che divergono non c'e'
modo di sapere quale dei due dica la verita'.
"""

from shinra.versione import numero as _numero

__version__ = _numero()

__all__ = ["__version__"]
