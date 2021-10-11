from datetime import datetime
import typing as tp
from uuid import UUID, uuid4

from botocore.client import BaseClient
from sqlalchemy import inspect, orm, text

from reports_service.db.models import Base, ReportsTable
from reports_service.models.report import Broker, ParseStatus


DBObjectCreator = tp.Callable[[Base], None]


def assert_all_tables_are_empty(
    db_session: orm.Session,
    exclude: tp.Collection[Base] = (),
) -> None:
    inspector = inspect(db_session.get_bind())
    tables_all = inspector.get_table_names()
    exclude_names = [e.__tablename__ for e in exclude]
    tables = set(tables_all) - (set(exclude_names) | {"alembic_version"})
    for table in tables:
        request = text(f"SELECT COUNT(*) FROM {table}")
        count = db_session.execute(request).fetchone()[0]
        assert count == 0


def clear_bucket(s3_client: BaseClient, bucket: str) -> None:
    buckets = [b["Name"] for b in s3_client.list_buckets()["Buckets"]]
    if bucket in buckets:
        objects = s3_client.list_objects(Bucket=bucket).get("Contents", [])
        for obj in objects:
            s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
        s3_client.delete_bucket(Bucket=bucket)


def make_db_report(
    report_id: tp.Optional[UUID] = None,
    user_id: tp.Optional[UUID] = None,
    filename: str = "some_filename",
    created_at: datetime = datetime(2021, 10, 11),
    parse_status: ParseStatus = ParseStatus.in_progress,
    broker: tp.Optional[Broker] = None,
    year: tp.Optional[int] = None,
) -> ReportsTable:
    return ReportsTable(
        report_id=str(report_id or uuid4()),
        user_id=str(user_id or uuid4()),
        filename=filename,
        created_at=created_at,
        parse_status=parse_status,
        broker=broker,
        year=year,
    )
