"""add_reports_table

Revision ID: 7a832704ff11
Revises:
Create Date: 2021-07-11 19:25:55.472593

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import (
    DATERANGE,
    SMALLINT,
    TIMESTAMP,
    UUID,
    VARCHAR,
)

from reports_service.db.models import parse_status_enum

# revision identifiers, used by Alembic.
revision = "7a832704ff11"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    parse_status_enum.create(op.get_bind())
    op.create_table(
        "reports",
        sa.Column("report_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("filename", VARCHAR(128), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("parse_status", parse_status_enum, nullable=False),
        sa.Column("parsed_at", TIMESTAMP, nullable=True),
        sa.Column("broker", VARCHAR(64), nullable=True, default=None),
        sa.Column("broker", broker_enum, nullable=True, default=None),
        sa.Column("period", DATERANGE, nullable=True, default=None),
        sa.Column("year", SMALLINT, nullable=True, default=None),
        sa.Column("parse_note", VARCHAR(256), nullable=True, default=None),
        sa.Column("parser_version", VARCHAR(64), nullable=True, default=None),

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
