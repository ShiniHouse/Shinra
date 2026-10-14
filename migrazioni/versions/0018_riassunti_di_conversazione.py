"""I riassunti delle conversazioni (issue #255, ADR 0010).

Si conservano i **riassunti**, non il testo grezzo: per profilo, con una scadenza, scritti dal codice a partire da cio' che e'
stato fatto e chiesto (mai dalle risposte libere del modello). Una tabella nuova, vuota: nessun profilo esistente ha
conversazioni conservate finche' non ne succede una.

Revision ID: b83f1a6d2c95
Revises: a52e7d9c1f40
Create Date: 2026-10-14 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b83f1a6d2c95"
down_revision: Union[str, Sequence[str], None] = "a52e7d9c1f40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "riassunti_conversazione",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("profilo", sa.String(length=64), nullable=False),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.Column("scade_il", sa.DateTime(), nullable=False),
        sa.Column("testo", sa.Text(), nullable=False),
        sa.Column("turni", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origine", sa.String(length=16), nullable=False, server_default="codice"),
        sa.Column("modello", sa.String(length=120), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("riassunti_conversazione", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_riassunti_conversazione_profilo"), ["profilo"], unique=False)
        batch_op.create_index(batch_op.f("ix_riassunti_conversazione_scade_il"), ["scade_il"], unique=False)


def downgrade() -> None:
    """Toglie la tabella: con lei se ne vanno i riassunti."""
    op.drop_table("riassunti_conversazione")
