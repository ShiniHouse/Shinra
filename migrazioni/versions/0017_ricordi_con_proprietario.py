"""Un ricordo ha un proprietario, un'origine, un'importanza e una storia (issue #245).

Sette colonne nuove nella tabella `knowledge`, piu' il luogo (#345, che condivide questa sola migrazione dello schema):

- `proprietario`: vuoto = della casa. **Tutti i ricordi esistenti restano della casa**: nessuno cambia di visibilita';
- `origine`: dei ricordi esistenti non si sa come siano nati (l'intervista usa lo stesso percorso di chi scrive a mano),
  quindi partono tutti `manuale`. Da adesso chi scrive dichiara la sua;
- `importanza` 1-5 (predefinita 3), `ultimo_uso` e `usi` (vuoti, a zero: si riempiono quando un ricordo serve);
- `stato`: `attivo`, tranne i ricordi gia' disattivati (`enabled` falso) che diventano `archiviato`: stessa cosa, detta con
  il nome nuovo. Il campo `enabled` resta com'e' e continua a valere;
- `aggiornato_il`: parte uguale a `creato_il`;
- `luogo_id`: vuoto.

Revision ID: a52e7d9c1f40
Revises: f19c4d7a3b82
Create Date: 2026-10-14 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a52e7d9c1f40"
down_revision: Union[str, Sequence[str], None] = "f19c4d7a3b82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("proprietario", sa.String(length=64), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("origine", sa.String(length=16), nullable=False, server_default="manuale")
        )
        batch_op.add_column(sa.Column("importanza", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("ultimo_uso", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("usi", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("stato", sa.String(length=12), nullable=False, server_default="attivo"))
        batch_op.add_column(sa.Column("aggiornato_il", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("luogo_id", sa.String(length=32), nullable=False, server_default=""))
        batch_op.create_index(batch_op.f("ix_knowledge_proprietario"), ["proprietario"], unique=False)

    # Il riempimento dei dati esistenti.
    op.execute("UPDATE knowledge SET aggiornato_il = creato_il")
    op.execute("UPDATE knowledge SET stato = 'archiviato' WHERE enabled = 0 OR enabled = 'false'")


def downgrade() -> None:
    """Toglie le colonne: i ricordi restano, senza proprietario ne' storia d'uso."""
    with op.batch_alter_table("knowledge", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_proprietario"))
        for colonna in (
            "luogo_id",
            "aggiornato_il",
            "stato",
            "usi",
            "ultimo_uso",
            "importanza",
            "origine",
            "proprietario",
        ):
            batch_op.drop_column(colonna)
