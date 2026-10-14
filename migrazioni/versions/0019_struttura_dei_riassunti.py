"""La struttura di un riassunto (issue #256).

Un riassunto nasce dal codice, dai fatti verificati. Per poter controllare una riscrittura fatta dal modello (che non deve
aggiungere nulla) si tiene accanto al testo cio' da cui nasce: le richieste e le azioni. Vuota per i riassunti gia' scritti:
quelli non si riscrivono.

Revision ID: c94a2e7b1d06
Revises: b83f1a6d2c95
Create Date: 2026-10-14 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c94a2e7b1d06"
down_revision: Union[str, Sequence[str], None] = "b83f1a6d2c95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("riassunti_conversazione", schema=None) as batch_op:
        batch_op.add_column(sa.Column("struttura", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("riassunti_conversazione", schema=None) as batch_op:
        batch_op.drop_column("struttura")
