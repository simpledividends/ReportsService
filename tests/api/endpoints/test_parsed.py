import typing as tp
from datetime import date
from decimal import Decimal
from http import HTTPStatus
from uuid import uuid4

import orjson
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import ReportRowsTable, ReportsTable
from reports_service.models.report import (
    DetailedReportRow,
    ParseStatus,
    PaymentStatus,
    SimpleReportRow,
)
from reports_service.models.user import UserRole
from reports_service.utils import utc_now
from tests.helpers import (
    DBObjectCreator,
    FakeAuthServer,
    assert_all_tables_are_empty,
    assert_forbidden,
    make_db_report,
    make_db_report_row,
    make_report_row,
)
from tests.utils import ApproxDatetime

UPLOAD_PARSED_REPORT_PATH_TEMPLATE = "/reports/{report_id}/parsed"
GET_REPORT_ROWS_PATH = "/reports/{report_id}/rows"
GET_DETAILED_REPORT_ROWS_PATH = "/reports/{report_id}/rows/detailed"


STANDARD_PARSING_RESULT_BODY: tp.Dict[str, tp.Any] = {
    "parsed_report": {
        "broker": "bbb",
        "version": "vvv",
        "period": (date(2020, 5, 10), date(2020, 9, 11)),
        "rows": [
            make_report_row(isin="isin1").dict(),
            make_report_row(isin="isin2", payed_tax_amount=None).dict(),
        ]
    },
    "is_parsed": True,
}
NOT_PARSED_PARSING_RESULT_BODY: tp.Dict[str, tp.Any] = {
        "parsed_report": None,
        "is_parsed": False,
    }


@pytest.mark.parametrize(
    "body,year,already_parsed",
    (
        (
            STANDARD_PARSING_RESULT_BODY,
            2020,
            False,
        ),
        (
            STANDARD_PARSING_RESULT_BODY,
            2020,
            True,
        ),
        (
            {
                "parsed_report": {
                    "broker": "bbb",
                    "version": "vvv",
                    "period": (date(2020, 5, 10), date(2021, 3, 11)),
                    "rows": []
                },
                "is_parsed": True,
            },
            None,
            True,
        ),
    )
)
def test_upload_parsed_report_success(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    body: tp.Dict[str, tp.Any],
    year: tp.Optional[int],
    already_parsed: bool,
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id, UserRole.service)

    report_id = uuid4()
    old_report = make_db_report(report_id=report_id, user_id=user_id, year=123)
    create_db_object(old_report)

    if already_parsed:
        for i in range(1, 4):
            create_db_object(make_db_report_row(report_id, row_n=i))

    now = utc_now()
    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=report_id),
            json=orjson.loads(orjson.dumps(body)),  # hack to serialize date
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK

    # Check report
    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    report = reports[0]
    assert report.broker == body["parsed_report"]["broker"]
    assert report.parser_version == body["parsed_report"]["version"]
    assert report.period_start == body["parsed_report"]["period"][0]
    assert report.period_end == body["parsed_report"]["period"][1]
    assert report.year == year
    assert report.parse_status == ParseStatus.parsed
    assert report.parsed_at == ApproxDatetime(now)
    assert report.price == Decimal('0')

    # Check rows
    rows = db_session.query(ReportRowsTable).all()
    expected_rows = body["parsed_report"]["rows"]
    isins = [row.isin for row in rows]
    expected_isins = [row["isin"] for row in expected_rows]
    assert sorted(isins) == sorted(expected_isins)
    row_numbers = [row.row_n for row in rows]
    assert row_numbers == list(range(1, len(expected_rows) + 1))


@pytest.mark.parametrize("prev_parsed_exists", (True, False))
def test_upload_not_parsed_report(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    prev_parsed_exists: bool,
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id, UserRole.service)

    report_id = uuid4()
    old_report = make_db_report(report_id=report_id, user_id=user_id, year=123)
    create_db_object(old_report)

    if prev_parsed_exists:
        create_db_object(make_db_report_row(report_id))

    body = NOT_PARSED_PARSING_RESULT_BODY

    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=report_id),
            json=body,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK

    # Check report
    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].year is None

    # Check rows
    rows = db_session.query(ReportRowsTable).all()
    assert len(rows) == 0


def test_upload_parsed_report_when_other_exists(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id, UserRole.service)

    report_id = uuid4()
    create_db_object(make_db_report(report_id=report_id, user_id=user_id))

    other_report_id = uuid4()
    other_report = make_db_report(
        report_id=other_report_id,
        user_id=user_id,
        year=2018,
    )
    create_db_object(other_report)
    for i in range(1, 4):
        create_db_object(make_db_report_row(other_report_id, row_n=i))

    body = STANDARD_PARSING_RESULT_BODY

    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=report_id),
            json=orjson.loads(orjson.dumps(body)),  # hack to serialize date
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK

    # Check report
    reports = db_session.query(ReportsTable).order_by(ReportsTable.year).all()
    assert len(reports) == 2
    assert reports[0].year == 2018
    assert reports[1].year == 2020

    # Check rows
    rows = (
        db_session
        .query(ReportRowsTable)
        .filter(ReportRowsTable.report_id == str(report_id))
        .all()
    )
    isins = [row.isin for row in rows]
    expected_isins = [row["isin"] for row in body["parsed_report"]["rows"]]
    assert sorted(isins) == sorted(expected_isins)

    other_report_rows = (
        db_session
        .query(ReportRowsTable)
        .filter(ReportRowsTable.report_id == str(other_report_id))
        .all()
    )
    assert len(other_report_rows) == 3


@pytest.mark.parametrize(
    "body",
    (
        STANDARD_PARSING_RESULT_BODY,
        NOT_PARSED_PARSING_RESULT_BODY,
    )
)
def test_upload_parsed_report_not_exists(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    db_session: orm.Session,
    body: tp.Dict[str, tp.Any],
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id, UserRole.service)

    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=uuid4()),
            json=orjson.loads(orjson.dumps(body)),  # hack to serialize date
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert_all_tables_are_empty(db_session)


@pytest.mark.parametrize(
    "body",
    (
        STANDARD_PARSING_RESULT_BODY,
        NOT_PARSED_PARSING_RESULT_BODY,
    )
)
def test_upload_parsed_report_is_deleted(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    body: tp.Dict[str, tp.Any],
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id, UserRole.service)
    report_id = uuid4()
    create_db_object(make_db_report(report_id, user_id, is_deleted=True))
    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=report_id),
            json=orjson.loads(orjson.dumps(body)),  # hack to serialize date
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert_all_tables_are_empty(db_session, [ReportsTable])


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_upload_report_forbidden_whet_not_authenticated(
    client: TestClient,
    headers: tp.Dict[str, str],
) -> None:
    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=uuid4()),
            json=NOT_PARSED_PARSING_RESULT_BODY,
            headers=headers,
        )
    assert_forbidden(resp)


@pytest.mark.parametrize("role", (UserRole.user, UserRole.admin))
def test_upload_report_forbidden_whet_not_service_role(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    role: UserRole,
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id, role)
    with client:
        resp = client.put(
            UPLOAD_PARSED_REPORT_PATH_TEMPLATE.format(report_id=uuid4()),
            json=NOT_PARSED_PARSING_RESULT_BODY,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert_forbidden(resp, "forbidden")


_PS = PaymentStatus


@pytest.mark.parametrize(
    "path,model,payment_status,price",
    (
        (GET_REPORT_ROWS_PATH, SimpleReportRow, _PS.payed, 100),
        (GET_REPORT_ROWS_PATH, SimpleReportRow, _PS.not_payed, 100),
        (GET_DETAILED_REPORT_ROWS_PATH, DetailedReportRow, _PS.payed, 100),
        (GET_DETAILED_REPORT_ROWS_PATH, DetailedReportRow, _PS.not_payed, 0),
        (GET_DETAILED_REPORT_ROWS_PATH, DetailedReportRow, _PS.error, 0),
        (GET_DETAILED_REPORT_ROWS_PATH, DetailedReportRow, _PS.in_progress, 0),
    )
)
@pytest.mark.parametrize("n_rows", (3, 0))
@pytest.mark.parametrize("year", (2022, None))
def test_get_report_rows_success(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    path: str,
    model: tp.Type,
    n_rows: int,
    year: tp.Optional[int],
    payment_status: PaymentStatus,
    price: float,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    other_report_id = uuid4()
    report = make_db_report(
        report_id,
        user_id=user_id,
        parse_status=ParseStatus.parsed,
        payment_status=PaymentStatus.payed,
    )
    create_db_object(report)
    other_report = make_db_report(
        other_report_id,
        user_id=user_id,
        parse_status=ParseStatus.parsed,
        payment_status=payment_status,
        price=Decimal(price),
    )
    create_db_object(other_report)
    for i in range(1, n_rows + 1):
        dt = date(2020 + i, 11, 5)
        row = make_db_report_row(report_id, i, name=f"a{i}", income_date=dt)
        create_db_object(row)
    create_db_object(make_db_report_row(other_report_id, row_n=1))

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.get(
            path.format(report_id=report_id),
            params={"year": year} if year is not None else {},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    rows = resp.json()["rows"]
    expected_keys = model.schema()["properties"].keys()
    for row in rows:
        assert set(row.keys()) == set(expected_keys)
        if model is DetailedReportRow:
            assert row["source_country_code"] == row["country_code"]
            assert row["target_country_code"] == "643"  # Russia

    name_key, name = (
        ("name", "a{i}")
        if model is SimpleReportRow
        else ("name_full", "isin a{i}")
    )
    if year is None:
        rng = range(1, n_rows + 1)
        assert [r[name_key] for r in rows] == [name.format(i=i) for i in rng]
        expected_years = ["2021", "2022", "2023"][:n_rows]
        assert [r["income_date"][:4] for r in rows] == expected_years
    else:
        if n_rows == 0:
            assert len(rows) == 0
        else:
            assert len(rows) == 1
            assert rows[0][name_key] == name.format(i=year - 2020)
            assert rows[0]["income_date"][:4] == str(year)


@pytest.mark.parametrize(
    "path",
    (GET_REPORT_ROWS_PATH, GET_DETAILED_REPORT_ROWS_PATH),
)
@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_get_report_rows_forbidden_when_not_authenticated(
    client: TestClient,
    headers: tp.Dict[str, str],
    path: str,
) -> None:
    with client:
        resp = client.get(
            path.format(report_id=uuid4()),
            headers=headers,
        )
    assert_forbidden(resp)


@pytest.mark.parametrize(
    "path",
    (GET_REPORT_ROWS_PATH, GET_DETAILED_REPORT_ROWS_PATH),
)
def test_get_report_rows_forbidden_when_foreign_report(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    path: str,
) -> None:
    user_id = uuid4()
    foreign_report_id = uuid4()
    foreign_report = make_db_report(
        foreign_report_id,
        user_id=uuid4(),
        parse_status=ParseStatus.parsed,
        payment_status=PaymentStatus.payed,
    )
    create_db_object(foreign_report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            path.format(report_id=foreign_report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert_forbidden(resp, "forbidden")


@pytest.mark.parametrize(
    "path",
    (GET_REPORT_ROWS_PATH, GET_DETAILED_REPORT_ROWS_PATH),
)
@pytest.mark.parametrize(
    "parse_status",
    (
        ParseStatus.in_progress,
        ParseStatus.not_parsed,
    )
)
def test_get_report_rows_when_not_parsed(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    parse_status: ParseStatus,
    path: str,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    report = make_db_report(
        report_id,
        user_id=user_id,
        parse_status=parse_status,
        payment_status=PaymentStatus.payed,
    )
    create_db_object(report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            path.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "path",
    (GET_REPORT_ROWS_PATH, GET_DETAILED_REPORT_ROWS_PATH),
)
def test_get_report_rows_when_not_exist(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    path: str,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            path.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "path",
    (GET_REPORT_ROWS_PATH, GET_DETAILED_REPORT_ROWS_PATH),
)
def test_get_report_rows_when_deleted(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    create_db_object: DBObjectCreator,
    path: str,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    create_db_object(make_db_report(report_id, user_id, is_deleted=True))
    with client:
        resp = client.get(
            path.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "payment_status",
    (
        PaymentStatus.in_progress,
        PaymentStatus.not_payed,
        PaymentStatus.error,
    )
)
def test_get_report_detailed_rows_when_not_payed(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    payment_status: PaymentStatus,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    report = make_db_report(
        report_id,
        user_id=user_id,
        parse_status=ParseStatus.parsed,
        payment_status=payment_status,
        price=Decimal(1),
    )
    create_db_object(report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            GET_DETAILED_REPORT_ROWS_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.PAYMENT_REQUIRED
