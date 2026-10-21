"""I lavori in background (issue #431, ADR 0013).

Una tabella nuova, vuota: una richiesta che prende tempo diventa un lavoro con proprietario, stato, avanzamento, tetto di tempo ed esito.
Contiene il testo della richiesta e dell'esito, quindi non esce nei salvataggi.

Revision ID: f28d6b1a3c49
Revises: e17c4a9d5b28
Create Date: 2026-10-22 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f28d6b1a3c49"
down_revision: Union[str, Sequence[str], None] = "e17c4a9d5b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lavori",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("proprietario", sa.String(length=64), nullable=False),
        sa.Column("scopo", sa.String(length=32), nullable=False, server_default="chat"),
        sa.Column("richiesta", sa.Text(), nullable=False),
        sa.Column("stato", sa.String(length=16), nullable=False, server_default="in_coda"),
        sa.Column("avanzamento", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fase", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("tetto_secondi", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("esito", sa.Text(), nullable=False, server_default=""),
        sa.Column("motivo", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("consegnato", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.Column("iniziato_il", sa.DateTime(), nullable=True),
        sa.Column("finito_il", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lavori", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_lavori_proprietario"), ["proprietario"], unique=False)
        batch_op.create_index(batch_op.f("ix_lavori_stato"), ["stato"], unique=False)


def downgrade() -> None:
    """Toglie la tabella: con lei se ne vanno i lavori, e quelli in corso non si possono piu' consegnare."""
    op.drop_table("lavori")
