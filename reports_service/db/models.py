from sqlalchemy import Column, ForeignKey, orm
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

from reports_service.models.report import ParseStatus, PaymentStatus

Base: DeclarativeMeta = declarative_base()

parse_status_enum = pg.ENUM(
    *ParseStatus.__members__.keys(),
    name="parse_status_enum",
    create_type=False,
)

payment_status_enum = pg.ENUM(
    *PaymentStatus.__members__.keys(),
    name="payment_status_enum",
    create_type=False,
)


class ReportsTable(Base):
    __tablename__ = "reports"

    report_id = Column(pg.UUID, primary_key=True)
    user_id = Column(pg.UUID, nullable=False)
    filename = Column(pg.VARCHAR(128), nullable=False)
    created_at = Column(pg.TIMESTAMP, nullable=False)
    payment_status = Column(
        payment_status_enum,
        nullable=False,
        server_default=PaymentStatus.not_payed,
    )
    price = Column("price", pg.NUMERIC(precision=7, scale=2), nullable=True)
    parse_status = Column(parse_status_enum, nullable=False)
    parsed_at = Column(pg.TIMESTAMP, nullable=True)
    broker = Column(pg.VARCHAR(64), nullable=True)
    period_start = Column(pg.DATE, nullable=True)
    period_end = Column(pg.DATE, nullable=True)
    year = Column(pg.SMALLINT, nullable=True)
    parse_note = Column(pg.VARCHAR(256), nullable=True)
    parser_version = Column(pg.VARCHAR(64), nullable=True)
    payment_status_updated_at = Column(pg.TIMESTAMP, nullable=True)
    is_deleted = Column(pg.BOOLEAN, nullable=False, server_default="0")
    deleted_at = Column(pg.TIMESTAMP, nullable=True)


class ReportRowsTable(Base):
    __tablename__ = "report_rows"

    report_id = Column(
        pg.UUID,
        ForeignKey(ReportsTable.report_id),
        primary_key=True,
    )
    row_n = Column(pg.INTEGER, primary_key=True)
    isin = Column(pg.VARCHAR(32), nullable=False)
    name = Column(pg.VARCHAR(256), nullable=False)
    tax_rate = Column(pg.VARCHAR(8), nullable=False)
    country_code = Column(pg.VARCHAR(8), nullable=False)
    income_amount = Column(pg.FLOAT, nullable=False)
    income_date = Column(pg.DATE, nullable=False)
    income_currency_rate = Column(pg.FLOAT, nullable=False)
    tax_payment_date = Column(pg.DATE, nullable=True)
    payed_tax_amount = Column(pg.FLOAT, nullable=True)
    tax_payment_currency_rate = Column(pg.FLOAT, nullable=True)

    report = orm.relationship(ReportsTable)
