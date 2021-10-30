"""add_reports_table

Revision ID: 7a832704ff11
Revises:
Create Date: 2021-07-11 19:25:55.472593

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import (
    BOOLEAN,
    DATE,
    NUMERIC,
    SMALLINT,
    TIMESTAMP,
    UUID,
    VARCHAR,
)

from reports_service.db.models import parse_status_enum, payment_status_enum
from reports_service.models.report import PaymentStatus

# revision identifiers, used by Alembic.
revision = "7a832704ff11"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    parse_status_enum.create(op.get_bind())
    payment_status_enum.create(op.get_bind())
    op.create_table(
        "reports",
        sa.Column("report_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("filename", VARCHAR(128), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("parse_status", parse_status_enum, nullable=False),
        sa.Column(
            "payment_status",
            payment_status_enum,
            nullable=False,
            server_default=PaymentStatus.not_payed,
        ),
        sa.Column("price", NUMERIC(precision=7, scale=2), nullable=True),
        sa.Column("parsed_at", TIMESTAMP, nullable=True),
        sa.Column("broker", VARCHAR(64), nullable=True),
        sa.Column("period_start", DATE, nullable=True),
        sa.Column("period_end", DATE, nullable=True),
        sa.Column("year", SMALLINT, nullable=True),
        sa.Column("parse_note", VARCHAR(256), nullable=True),
        sa.Column("parser_version", VARCHAR(64), nullable=True),
        sa.Column("is_deleted", BOOLEAN, nullable=False, server_default="0"),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),

        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index(
        op.f("ix_reports_user_id"),
        "reports",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_reports_user_id"), table_name="users")
    op.drop_table("reports")
    op.execute("DROP TYPE parse_status_enum")
    op.execute("DROP TYPE payment_status_enum")
