"""add_report_rows_table

Revision ID: 9986a3a7aea0
Revises: 7a832704ff11
Create Date: 2021-10-16 15:16:16.046584

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import DATE, FLOAT, INTEGER, UUID, VARCHAR

# revision identifiers, used by Alembic.
revision = '9986a3a7aea0'
down_revision = '7a832704ff11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_rows",
        sa.Column("report_id", UUID, primary_key=True),
        sa.Column("row_n", INTEGER, primary_key=True),
        sa.Column("isin", VARCHAR(32), nullable=False),
        sa.Column("name", VARCHAR(256), nullable=False),
        sa.Column("tax_rate", VARCHAR(8), nullable=False),
        sa.Column("country_code", VARCHAR(8), nullable=False),
        sa.Column("currency_code", VARCHAR(8), nullable=False),
        sa.Column("income_amount", FLOAT, nullable=False),
        sa.Column("income_date", DATE, nullable=False),
        sa.Column("income_currency_rate", FLOAT, nullable=False),
        sa.Column("tax_payment_date", DATE, nullable=True),
        sa.Column("payed_tax_amount", FLOAT, nullable=True),
        sa.Column("tax_payment_currency_rate", FLOAT, nullable=True),

        sa.PrimaryKeyConstraint("report_id", "row_n"),
        sa.ForeignKeyConstraint(
            columns=("report_id",),
            refcolumns=("reports.report_id",),
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("report_rows")
