"""Storico dei contatori di energia (issue #24).

Si conservano le letture grezze e non i consumi gia' calcolati: il consumo di
un'ora e' una differenza fra due letture, le differenze si ricalcolano, le
letture perdute no. La fascia invece si scrive, perche' ARERA puo' cambiare
gli orari e una bolletta di due anni fa deve restare divisa come lo era
allora.

Revision ID: 3a1f57c9e204
Revises: d724da79dbd8
Create Date: 2026-09-09 10:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a1f57c9e204"
down_revision: Union[str, Sequence[str], None] = "d724da79dbd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella."""
    op.create_table(
        "letture_energia",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("momento", sa.DateTime(), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=False),
        sa.Column("valore", sa.Float(), nullable=False),
        sa.Column("consumo", sa.Float(), nullable=False),
        sa.Column("fascia", sa.String(length=4), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("letture_energia", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_letture_energia_momento"), ["momento"], unique=False)
        batch_op.create_index(batch_op.f("ix_letture_energia_entity_id"), ["entity_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_letture_energia_fascia"), ["fascia"], unique=False)


def downgrade() -> None:
    """La rimuove: lo storico dei consumi va perduto, i sensori no."""
    with op.batch_alter_table("letture_energia", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_letture_energia_fascia"))
        batch_op.drop_index(batch_op.f("ix_letture_energia_entity_id"))
        batch_op.drop_index(batch_op.f("ix_letture_energia_momento"))

    op.drop_table("letture_energia")
