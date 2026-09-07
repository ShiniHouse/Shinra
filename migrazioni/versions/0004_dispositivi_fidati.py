"""Dispositivi fidati (issue #20).

Della credenziale si conserva solo l'impronta, come per i PIN: se il
database finisse dove non deve, queste righe non aprirebbero nessuna casa.

Revision ID: d724da79dbd8
Revises: 16be1a50615c
Create Date: 2026-09-07 14:41:12.951742

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d724da79dbd8"
down_revision: Union[str, Sequence[str], None] = "16be1a50615c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella."""
    op.create_table(
        "dispositivi_fidati",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("impronta", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.Column("ultimo_uso", sa.DateTime(), nullable=False),
        sa.Column("ultimo_indirizzo", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("dispositivi_fidati", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_dispositivi_fidati_impronta"), ["impronta"], unique=False)
        batch_op.create_index(batch_op.f("ix_dispositivi_fidati_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    """La rimuove: tutti i dispositivi tornano a chiedere il PIN."""
    with op.batch_alter_table("dispositivi_fidati", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_dispositivi_fidati_user_id"))
        batch_op.drop_index(batch_op.f("ix_dispositivi_fidati_impronta"))

    op.drop_table("dispositivi_fidati")
