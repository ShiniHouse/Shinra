"""Le proposte del sogno notturno (issue #259, #261, #263).

Una tabella nuova, vuota: le proposte (abitudini notate, ricordi doppi o in contraddizione) nascono di notte e aspettano che
una persona le accetti o le scarti. Contengono dati verificati dal codice, non frasi.

Revision ID: d05b3f8c2e17
Revises: c94a2e7b1d06
Create Date: 2026-10-19 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d05b3f8c2e17"
down_revision: Union[str, Sequence[str], None] = "c94a2e7b1d06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposte_del_sogno",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("profilo", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("chiave", sa.String(length=200), nullable=False),
        sa.Column("dati", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("stato", sa.String(length=16), nullable=False, server_default="nuova"),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.Column("deciso_il", sa.DateTime(), nullable=True),
        sa.Column("scade_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("proposte_del_sogno", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_proposte_del_sogno_profilo"), ["profilo"], unique=False)
        batch_op.create_index(batch_op.f("ix_proposte_del_sogno_scade_il"), ["scade_il"], unique=False)


def downgrade() -> None:
    """Toglie la tabella: con lei se ne vanno le proposte, che la notte dopo si rifanno."""
    op.drop_table("proposte_del_sogno")
