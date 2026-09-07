"""Registro azioni: durata, correlazione, e via il vincolo sull'attore.

La tabella era nata vuota con lo schema iniziale (issue #12) e nessuna
versione rilasciata ci ha mai scritto dentro: qui viene ricreata, non
migrata, e non si perde nulla.

Tre cambiamenti:

- `durata_ms` e `correlazione`, che la issue #15 chiede: quanto e' durata
  l'operazione e a quale richiesta apparteneva.
- **Via la chiave esterna su `users.id`.** Con quel vincolo il database
  rifiutava le righe di chi non e' in anagrafica — un ospite che parla
  all'Echo, un profilo cancellato dopo il fatto — cioe' proprio le azioni
  che piu' interessa ritrovare. E le rifiutava in silenzio, perche' il
  registro non solleva mai per non fermare la casa.

Revision ID: 27755ef706bb
Revises: cedef94ed840
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27755ef706bb"
down_revision: Union[str, Sequence[str], None] = "cedef94ed840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ricrea la tabella nella forma definitiva."""
    op.drop_index("ix_registro_azioni_azione", table_name="registro_azioni")
    op.drop_index("ix_registro_azioni_momento", table_name="registro_azioni")
    op.drop_table("registro_azioni")

    op.create_table(
        "registro_azioni",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("momento", sa.DateTime(), nullable=False),
        sa.Column("attore", sa.String(length=64), nullable=True),
        sa.Column("canale", sa.String(length=32), nullable=False),
        sa.Column("azione", sa.String(length=120), nullable=False),
        sa.Column("dettagli", sa.JSON(), nullable=False),
        sa.Column("esito", sa.String(length=32), nullable=False),
        sa.Column("durata_ms", sa.Integer(), nullable=True),
        sa.Column("correlazione", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registro_azioni_momento", "registro_azioni", ["momento"])
    op.create_index("ix_registro_azioni_azione", "registro_azioni", ["azione"])
    op.create_index("ix_registro_azioni_attore", "registro_azioni", ["attore"])
    op.create_index("ix_registro_azioni_correlazione", "registro_azioni", ["correlazione"])


def downgrade() -> None:
    """Torna alla tabella vuota dello schema iniziale."""
    op.drop_index("ix_registro_azioni_correlazione", table_name="registro_azioni")
    op.drop_index("ix_registro_azioni_attore", table_name="registro_azioni")
    op.drop_index("ix_registro_azioni_azione", table_name="registro_azioni")
    op.drop_index("ix_registro_azioni_momento", table_name="registro_azioni")
    op.drop_table("registro_azioni")

    op.create_table(
        "registro_azioni",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("momento", sa.DateTime(), nullable=False),
        sa.Column("attore", sa.String(length=64), nullable=True),
        sa.Column("canale", sa.String(length=32), nullable=False),
        sa.Column("azione", sa.String(length=120), nullable=False),
        sa.Column("dettagli", sa.JSON(), nullable=False),
        sa.Column("esito", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["attore"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registro_azioni_momento", "registro_azioni", ["momento"])
    op.create_index("ix_registro_azioni_azione", "registro_azioni", ["azione"])
