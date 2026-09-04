"""Persistenza di Shinra: un file SQLite al posto di sei file JSON."""

from core.archivio.motore import percorso_archivio, reimposta, sessione

__all__ = ["percorso_archivio", "reimposta", "sessione"]
