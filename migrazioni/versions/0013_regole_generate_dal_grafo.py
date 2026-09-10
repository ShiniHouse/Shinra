"""Da dove viene una regola (issue #28).

Un grafo con un innesco all'alba diventa **una regola del motore della #27**,
non un secondo scheduler: due motori che programmano la stessa casa si
contendono lo stesso lavoro, e il secondo si scopre solo quando la luce si
accende due volte.

Perche' cio' funzioni serve sapere quali regole sono nate cosi'. Senza,
risalvare una routine lascerebbe dietro la regola di prima — un lavoro
programmato che nessuno rivendica, e che continua a scattare quando ormai il
disegno dice un'altra cosa. E' il difetto piu' difficile da diagnosticare:
qualcosa si accende e non c'e' niente che lo spieghi.

`origine` e' vuota per le regole scritte a mano, e vale `grafo:<id modalita>`
per quelle generate.

Revision ID: c1f70b62d945
Revises: e4a91c07b3d8
Create Date: 2026-09-10 14:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1f70b62d945"
down_revision: Union[str, Sequence[str], None] = "e4a91c07b3d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("regole", schema=None) as batch_op:
        batch_op.add_column(sa.Column("origine", sa.String(length=96), nullable=False, server_default=""))


def downgrade() -> None:
    """Toglie la colonna. Le regole generate restano, e da qui in poi
    sembrano scritte a mano: e' l'unica perdita possibile, e va detta."""
    with op.batch_alter_table("regole", schema=None) as batch_op:
        batch_op.drop_column("origine")
