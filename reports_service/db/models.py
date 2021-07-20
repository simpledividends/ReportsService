from sqlalchemy import Column
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

from reports_service.models.report import Broker, ParseStatus

Base: DeclarativeMeta = declarative_base()

broker_enum = pg.ENUM(
    *Broker.__members__.keys(),
    name="broker_enum",
    create_type=False,
)

parse_status_enum = pg.ENUM(
    *ParseStatus.__members__.keys(),
    name="parse_status_enum",
    create_type=False,
)


class ReportsTable(Base):
    __tablename__ = "reports"

    report_id = Column(pg.UUID, primary_key=True)
    user_id = Column(pg.UUID, nullable=False)
    filename = Column(pg.VARCHAR(128), nullable=False)
    created_at = Column(pg.TIMESTAMP, nullable=False)
    parse_status = Column(parse_status_enum, nullable=False)
    broker = Column(broker_enum, nullable=True, default=None)
    year = Column(pg.SMALLINT, nullable=True, default=None)
