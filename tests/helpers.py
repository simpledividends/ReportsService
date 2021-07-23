import typing as tp

from botocore.client import BaseClient
from sqlalchemy import inspect, orm, text

from reports_service.db.models import Base


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
