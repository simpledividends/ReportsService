import typing as tp
from datetime import date, datetime
from http import HTTPStatus
from uuid import UUID, uuid4

import orjson
import werkzeug
from botocore.client import BaseClient
from requests import Response
from sqlalchemy import inspect, orm, text

from reports_service.auth import AUTH_SERVISE_AUTHORIZATION_HEADER
from reports_service.db.models import Base, ReportRowsTable, ReportsTable
from reports_service.models.report import ParseStatus, ParsedReportRow
from reports_service.models.user import UserRole

DBObjectCreator = tp.Callable[[Base], None]


class FakeAuthServer:

    def __init__(self) -> None:
        self.ok_responses: tp.Dict[str, tp.Tuple[UUID, UserRole]] = {}

    def add_ok_response(
        self,
        token: str,
        user_id: UUID,
        role: UserRole = UserRole.user,
    ) -> None:
        self.ok_responses[token] = (user_id, role)  # token -> (user_id, role)

    def handle_get_user_request(
        self,
        request: werkzeug.Request,
    ) -> werkzeug.Response:
        header = request.headers.get(AUTH_SERVISE_AUTHORIZATION_HEADER, "")
        splitted = header.split()
        if (
            len(splitted) == 2
            and splitted[0] == "Bearer"
            and splitted[1] in self.ok_responses
        ):
            user_id, role = self.ok_responses[splitted[1]]
            body = {
                "user_id": user_id,
                "email": "user@ma.il",
                "name": "user name",
                "created_at": datetime(2021, 10, 11),
                "verified_at": datetime(2021, 6, 11),
                "role": role,
            }
            status_code = HTTPStatus.OK
        else:
            body = {
                "errors": [
                    {
                        "error_key": "forbidden!",
                        "error_message": "Forbidden",
                    }
                ]
            }
            status_code = HTTPStatus.FORBIDDEN
        return werkzeug.Response(
                orjson.dumps(body),
                status=status_code,
                content_type="application/json"
            )


def assert_forbidden(resp: Response, error_key: str = "forbidden!") -> None:
    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()["errors"][0]["error_key"] == error_key


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
    broker: tp.Optional[str] = None,
    year: tp.Optional[int] = None,
    is_deleted: bool = False,
    deleted_at: tp.Optional[datetime] = None,
) -> ReportsTable:
    return ReportsTable(
        report_id=str(report_id or uuid4()),
        user_id=str(user_id or uuid4()),
        filename=filename,
        created_at=created_at,
        parse_status=parse_status,
        broker=broker,
        year=year,
        is_deleted=is_deleted,
        deleted_at=deleted_at,
    )


def make_db_report_row(
    report_id: tp.Optional[UUID] = None,
    row_n: int = 1,
    isin: str = "isin",
    name: str = "name",
) -> ReportRowsTable:
    return ReportRowsTable(
        report_id=str(report_id or uuid4()),
        row_n=row_n,
        isin=isin,
        name=name,
        tax_rate="13",
        country_code="840",
        income_amount=15.3,
        income_date=date(2020, 10, 16),
        income_currency_rate=77.7,
        tax_payment_date=date(2020, 10, 16),
        payed_tax_amount=2.3,
        tax_payment_currency_rate=77.7,
    )


def make_report_row(
    isin: str = "isin",
    payed_tax_amount: tp.Optional[float] = 2.3,
) -> ParsedReportRow:
    return ParsedReportRow(
        isin=isin,
        name="name",
        tax_rate="13",
        country_code="840",
        income_amount=15.3,
        income_date=date(2020, 10, 16),
        income_currency_rate=77.7,
        tax_payment_date=date(2020, 10, 16),
        payed_tax_amount=payed_tax_amount,
        tax_payment_currency_rate=77.7,
    )
