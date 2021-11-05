"""add_promocodes_table

Revision ID: 4363041b49d1
Revises: 9986a3a7aea0
Create Date: 2021-11-04 17:20:03.256663

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INTEGER, TIMESTAMP, UUID, VARCHAR

# revision identifiers, used by Alembic.
revision = '4363041b49d1'
down_revision = '9986a3a7aea0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promocodes",
        sa.Column("promocode", VARCHAR(16), primary_key=True),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("valid_from", TIMESTAMP, nullable=False),
        sa.Column("valid_to", TIMESTAMP, nullable=False),
        sa.Column("rest_usages", INTEGER, nullable=False),
        sa.Column("discount", INTEGER, nullable=False),

        sa.PrimaryKeyConstraint("promocode"),
    )


def downgrade():
    op.drop_table("promocodes")
