"""Configurazione comune della suite di test.

Finche' il codice non e' sotto `src/shinra/` (issue #16, milestone v0.2.0) la
radice del progetto va aggiunta a sys.path perche' `import core` risolva.
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))
