"""La lingua di ciascuna persona (issue #36).

Finora la lingua era una sola per installazione (`assistant.language`). Due
persone della stessa casa possono parlare lingue diverse: la scelta sta nel
profilo. Vuota vuol dire «quella dell'installazione», quindi nessuno dei
profili esistenti cambia comportamento.

Revision ID: d8a3f61c2b07
Revises: c1f70b62d945
Create Date: 2026-09-30 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8a3f61c2b07"
down_revision: Union[str, Sequence[str], None] = "c1f70b62d945"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lingua", sa.String(length=16), nullable=False, server_default=""))


def downgrade() -> None:
    """Toglie la colonna: le persone tornano tutte alla lingua dell'installazione."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("lingua")
