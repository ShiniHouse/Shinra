"""Liste, calendario e scadenze di manutenzione (issue #25).

Tre tabelle che nascono vuote e possono restare vuote: liste ed eventi
esistono come alternativa a Home Assistant, non come copia. Dove c'e' una
lista `todo` o un calendario `calendar`, si legge e si scrive li'.

Le scadenze invece sono sempre di casa: Home Assistant non ha un dominio per
«il bollo scade a marzo».

Revision ID: 8c2e4b1a7f30
Revises: 3a1f57c9e204
Create Date: 2026-09-09 11:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c2e4b1a7f30"
down_revision: Union[str, Sequence[str], None] = "3a1f57c9e204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea le quattro tabelle."""
    op.create_table(
        "liste",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("creata_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("liste", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_liste_nome"), ["nome"], unique=False)

    op.create_table(
        "voci_lista",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("lista_id", sa.String(length=32), nullable=False),
        sa.Column("testo", sa.String(length=240), nullable=False),
        sa.Column("fatta", sa.Boolean(), nullable=False),
        sa.Column("autore", sa.String(length=64), nullable=True),
        sa.Column("aggiunta_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("voci_lista", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_voci_lista_lista_id"), ["lista_id"], unique=False)

    op.create_table(
        "eventi_calendario",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("titolo", sa.String(length=240), nullable=False),
        sa.Column("inizio", sa.DateTime(), nullable=False),
        sa.Column("fine", sa.DateTime(), nullable=True),
        sa.Column("tutto_il_giorno", sa.Boolean(), nullable=False),
        sa.Column("luogo", sa.String(length=160), nullable=False),
        sa.Column("autore", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("eventi_calendario", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_eventi_calendario_inizio"), ["inizio"], unique=False)

    op.create_table(
        "scadenze",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("titolo", sa.String(length=240), nullable=False),
        sa.Column("prossima", sa.DateTime(), nullable=False),
        sa.Column("ogni", sa.Integer(), nullable=False),
        sa.Column("unita", sa.String(length=16), nullable=False),
        sa.Column("preavviso", sa.Integer(), nullable=False),
        sa.Column("documento", sa.String(length=500), nullable=False),
        sa.Column("ultima_fatta", sa.DateTime(), nullable=True),
        sa.Column("promemoria_id", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scadenze", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scadenze_prossima"), ["prossima"], unique=False)


def downgrade() -> None:
    """Le rimuove. Cio' che sta in Home Assistant resta dov'e'."""
    with op.batch_alter_table("scadenze", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scadenze_prossima"))
    op.drop_table("scadenze")

    with op.batch_alter_table("eventi_calendario", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_eventi_calendario_inizio"))
    op.drop_table("eventi_calendario")

    with op.batch_alter_table("voci_lista", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_voci_lista_lista_id"))
    op.drop_table("voci_lista")

    with op.batch_alter_table("liste", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_liste_nome"))
    op.drop_table("liste")
