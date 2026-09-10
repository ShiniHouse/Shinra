"""Il disegno dell'editor a nodi finalmente si salva (issue #28).

Le due colonne non c'erano. L'editor a grafo mandava `nodes` ed `edges` al
salvataggio, il deposito copiava solo i campi che conosceva, e il disegno
spariva: nessun errore, nessun avviso. Di conseguenza l'esecutore non ha mai
visto un grafo in produzione, e le sue novanta righe di visita in ampiezza
erano codice irraggiungibile.

Nascono vuote. Le routine esistenti hanno il loro elenco lineare di `actions`
e continuano a funzionare da li': la migrazione non prova a dedurre un grafo
da un elenco, perche' un grafo dedotto male e' peggio di un grafo assente —
si aprirebbe nell'editor come se fosse quello che qualcuno aveva disegnato.

Revision ID: e4a91c07b3d8
Revises: b6e3d18a4c72
Create Date: 2026-09-10 11:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4a91c07b3d8"
down_revision: Union[str, Sequence[str], None] = "b6e3d18a4c72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("modes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("nodes", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("edges", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    """Toglie le colonne, e con esse i disegni: le routine tornano a valere
    per il loro elenco di azioni."""
    with op.batch_alter_table("modes", schema=None) as batch_op:
        batch_op.drop_column("edges")
        batch_op.drop_column("nodes")
