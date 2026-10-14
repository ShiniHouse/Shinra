"""Da dove si sa dove e' una persona (issue #343).

Ogni profilo puo' collegare la persona o il telefono di Home Assistant da cui si legge la sua posizione. **Vuota vuol dire
posizione spenta**: nessun profilo esistente cambia comportamento, e nessuno e' localizzato senza averlo scelto. Si salva il
nome dell'entita', non dove si trova la persona: la posizione si legge al momento, mai si conserva.

Revision ID: f19c4d7a3b82
Revises: e4b8c20a71d3
Create Date: 2026-10-14 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f19c4d7a3b82"
down_revision: Union[str, Sequence[str], None] = "e4b8c20a71d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("entita_posizione", sa.String(length=120), nullable=False, server_default=""))


def downgrade() -> None:
    """Toglie la colonna: nessuno e' piu' localizzato."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("entita_posizione")
