"""Gli identificativi dei ricordi cancellati (ADR 0009, punto 6).

Una tabella nuova, vuota: un ripristino da un salvataggio vecchio non riporta in casa un ricordo cancellato dopo quel
salvataggio. Contiene solo l'identificativo e il momento, mai il testo.

Revision ID: e17c4a9d5b28
Revises: d05b3f8c2e17
Create Date: 2026-10-21 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e17c4a9d5b28"
down_revision: Union[str, Sequence[str], None] = "d05b3f8c2e17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ricordi_cancellati",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cancellato_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Toglie la tabella: da quel momento un ripristino vecchio puo' di nuovo riportare un ricordo cancellato."""
    op.drop_table("ricordi_cancellati")
