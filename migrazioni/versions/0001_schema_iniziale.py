"""Schema iniziale: le sette tabelle che sostituiscono i sei file JSON.

Nasce gia' con `registro_azioni`, che resta vuota fino alla issue #15:
crearla adesso costa nulla, crearla dopo sarebbe una seconda migrazione sul
database di una casa in funzione.

Revision ID: cedef94ed840
Revises: nessuna (e' la prima)
Create Date: 2026-09-04 14:07:10.112549

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cedef94ed840"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea le tabelle."""
    op.create_table(
        "device_aliases",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=160), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=False),
        sa.Column("room", sa.String(length=80), nullable=True),
        sa.Column("domain", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("device_aliases", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_device_aliases_alias"), ["alias"], unique=False)

    op.create_table(
        "knowledge",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("knowledge", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_knowledge_category"), ["category"], unique=False)

    op.create_table(
        "modes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=True),
        sa.Column("trigger_phrases", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("remind_at", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("completed_at", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("reminders", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reminders_completed"), ["completed"], unique=False)
        batch_op.create_index(batch_op.f("ix_reminders_remind_at"), ["remind_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_reminders_user_id"), ["user_id"], unique=False)

    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sources", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sources_category"), ["category"], unique=False)

    op.create_table(
        "timers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("timers", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_timers_completed"), ["completed"], unique=False)
        batch_op.create_index(batch_op.f("ix_timers_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_timers_user_id"), ["user_id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("age_group", sa.String(length=32), nullable=False),
        sa.Column("gender", sa.String(length=32), nullable=False),
        sa.Column("avatar_type", sa.String(length=32), nullable=True),
        sa.Column("pin", sa.String(length=255), nullable=True),
        sa.Column("preferred_news_categories", sa.JSON(), nullable=False),
        sa.Column("restricted_topics", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.Column("aggiornato_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "registro_azioni",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("momento", sa.DateTime(), nullable=False),
        sa.Column("attore", sa.String(length=64), nullable=True),
        sa.Column("canale", sa.String(length=32), nullable=False),
        sa.Column("azione", sa.String(length=120), nullable=False),
        sa.Column("dettagli", sa.JSON(), nullable=False),
        sa.Column("esito", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["attore"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("registro_azioni", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_registro_azioni_azione"), ["azione"], unique=False)
        batch_op.create_index(batch_op.f("ix_registro_azioni_momento"), ["momento"], unique=False)


def downgrade() -> None:
    """Le rimuove. I file JSON restano al loro posto: sono il ritorno indietro vero."""
    with op.batch_alter_table("registro_azioni", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_registro_azioni_momento"))
        batch_op.drop_index(batch_op.f("ix_registro_azioni_azione"))

    op.drop_table("registro_azioni")
    op.drop_table("users")
    with op.batch_alter_table("timers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_timers_user_id"))
        batch_op.drop_index(batch_op.f("ix_timers_expires_at"))
        batch_op.drop_index(batch_op.f("ix_timers_completed"))

    op.drop_table("timers")
    with op.batch_alter_table("sources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sources_category"))

    op.drop_table("sources")
    with op.batch_alter_table("reminders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reminders_user_id"))
        batch_op.drop_index(batch_op.f("ix_reminders_remind_at"))
        batch_op.drop_index(batch_op.f("ix_reminders_completed"))

    op.drop_table("reminders")
    op.drop_table("modes")
    with op.batch_alter_table("knowledge", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_category"))

    op.drop_table("knowledge")
    with op.batch_alter_table("device_aliases", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_device_aliases_alias"))

    op.drop_table("device_aliases")
