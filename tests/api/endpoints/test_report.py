import base64
import os.path
import typing as tp
from datetime import datetime
from http import HTTPStatus
from tempfile import NamedTemporaryFile
from uuid import uuid4

import orjson
import pytest
from botocore.client import BaseClient
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import ReportRowsTable, ReportsTable
from reports_service.models.report import ParseStatus
from reports_service.settings import ServiceConfig
from reports_service.utils import utc_now
from tests.helpers import (
    DBObjectCreator,
    FakeAuthServer,
    assert_all_tables_are_empty,
    assert_forbidden,
    make_db_report,
    make_db_report_row,
)
from tests.utils import AnyUUID, ApproxDatetime

UPLOAD_REPORT_PATH = "/reports"
GET_REPORTS_PATH = "/reports"
GET_REPORT_PATH = "/reports/{report_id}"
DELETE_REPORT_PATH = "/reports/{report_id}"


def test_upload_report_success(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    db_session: orm.Session,
    s3_client: BaseClient,
    sqs_client: BaseClient,
    service_config: ServiceConfig,
    sqs_queue_url: str,
) -> None:
    access_token = "some_token"
    user_id = uuid4()
    fake_auth_server.add_ok_response(access_token, user_id)

    now = utc_now()
    body = b"some data"
    request_id = "some_request_id"
    with NamedTemporaryFile("w+b") as f:
        filename = os.path.basename(f.name)
        f.write(body)
        f.seek(0)
        with client:
            resp = client.post(
                UPLOAD_REPORT_PATH,
                files={"file": f},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    service_config.request_id_header: request_id,
                }
            )

    # Check response
    assert resp.status_code == HTTPStatus.CREATED
    resp_json = resp.json()
    assert resp_json == {
        "report_id": AnyUUID(),
        "user_id": str(user_id),
        "filename": filename,
        "created_at": ApproxDatetime(now),
        "parse_status": ParseStatus.in_progress,
        "parsed_at": None,
        "broker": None,
        "period": None,
        "year": None,
        "parse_note": None,
        "parser_version": None,
    }

    # Check DB content
    assert_all_tables_are_empty(db_session, [ReportsTable])
    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    report = reports[0]
    report_dict = orjson.loads(
        orjson.dumps(
            {k: getattr(report, k) for k in resp_json.keys() if k != "period"}
        )
    )
    resp_json.pop("period")
    assert report_dict == resp_json
    assert report.period_start is None
    assert report.period_end is None

    # Check report body in storage
    bucket = service_config.storage_config.bucket
    objects = s3_client.list_objects(Bucket=bucket)["Contents"]
    assert len(objects) == 1
    key = service_config.storage_config.report_body_key_template.format(
        report_id=resp_json["report_id"]
    )
    with NamedTemporaryFile("w+b") as f:
        s3_client.download_fileobj(bucket, key, f)
        f.seek(0)
        assert f.read() == body

    # Check parse message in queue
    messages = (
        sqs_client.receive_message(
            QueueUrl=sqs_queue_url,
            MaxNumberOfMessages=10,
        )
        .get('Messages', [])
    )
    assert len(messages) == 1
    message = messages[0]
    msg_content = orjson.loads(base64.b64decode(message["Body"].encode()))
    headers = msg_content["headers"]
    assert headers["task"] == service_config.queue_config.parse_task
    assert headers["id"] == AnyUUID()
    msg_body = msg_content["body"]
    msg_body_content = orjson.loads(base64.b64decode(msg_body.encode()))
    msg_body_kwargs = msg_body_content[1]
    expected_body_kwargs = {
        "storage_key": key,
        "request_id": request_id,
        "report_id": str(report.report_id),
        }
    assert msg_body_kwargs == expected_body_kwargs


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_upload_report_forbidden(
    client: TestClient,
    headers: tp.Dict[str, str],
) -> None:
    with NamedTemporaryFile("w+b") as f:
        f.write(b"some data")
        f.seek(0)
        with client:
            resp = client.post(
                UPLOAD_REPORT_PATH,
                files={"file": f},
                headers=headers,
            )
    assert_forbidden(resp)


def test_get_reports_success(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_1_id = uuid4()
    user_2_id = uuid4()
    create_db_object(make_db_report(user_id=user_1_id, filename="report_1"))
    create_db_object(make_db_report(user_id=user_2_id, filename="report_2"))
    create_db_object(make_db_report(user_id=user_1_id, filename="report_3"))
    deleted_report = make_db_report(
        user_id=user_1_id,
        filename="report_4",
        is_deleted=True,
    )
    create_db_object(deleted_report)

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_1_id)

    with client:
        resp = client.get(
            GET_REPORTS_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    reports = resp.json()["reports"]
    report_names = [r["filename"] for r in reports]
    assert sorted(report_names) == ["report_1", "report_3"]


def test_get_reports_when_no_user_reports(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_1_id = uuid4()
    user_2_id = uuid4()
    create_db_object(make_db_report(user_id=user_2_id, filename="report_2"))

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_1_id)

    with client:
        resp = client.get(
            GET_REPORTS_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()["reports"]) == 0


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_get_reports_forbidden(
    client: TestClient,
    create_db_object: DBObjectCreator,
    headers: tp.Dict[str, str],
) -> None:
    create_db_object(make_db_report())
    with client:
        resp = client.get(
            GET_REPORTS_PATH,
            headers=headers,
        )
    assert_forbidden(resp)


def test_get_report_success(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_1_id = uuid4()
    user_2_id = uuid4()
    report = make_db_report(user_id=user_1_id, filename="report_1")
    create_db_object(report)
    create_db_object(make_db_report(user_id=user_2_id, filename="report_2"))
    create_db_object(make_db_report(user_id=user_1_id, filename="report_3"))

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_1_id)

    with client:
        resp = client.get(
            GET_REPORT_PATH.format(report_id=report.report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    resp_dict = resp.json()
    assert resp_dict["filename"] == "report_1"
    assert resp_dict["report_id"] == report.report_id
    assert resp_dict["user_id"] == str(user_1_id)


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_get_report_forbidden_when_not_authenticated(
    client: TestClient,
    headers: tp.Dict[str, str],
) -> None:
    with client:
        resp = client.get(
            GET_REPORTS_PATH.format(report_id=uuid4()),
            headers=headers,
        )
    assert_forbidden(resp)


def test_get_report_forbidden_when_foreign_report(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    foreign_report_id = uuid4()
    foreign_report = make_db_report(
        foreign_report_id,
        user_id=uuid4(),
        parse_status=ParseStatus.parsed,
    )
    create_db_object(foreign_report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            GET_REPORT_PATH.format(report_id=foreign_report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert_forbidden(resp, "forbidden")


def test_get_report_when_not_exist(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            GET_REPORT_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_get_report_when_deleted(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    create_db_object: DBObjectCreator,
) -> None:
    user_id = uuid4()
    report = make_db_report(user_id=user_id, is_deleted=True)
    create_db_object(report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            GET_REPORT_PATH.format(report_id=report.report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("n_rows", (3, 0))
def test_delete_report_success(
    client: TestClient,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    n_rows: int,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    other_report_id = uuid4()
    create_db_object(make_db_report(report_id, user_id=user_id, filename="a"))
    create_db_object(make_db_report(other_report_id, user_id=user_id))
    for i in range(1, n_rows + 1):
        create_db_object(make_db_report_row(report_id, row_n=i))
    create_db_object(make_db_report_row(other_report_id, row_n=1, name="nnn"))

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.delete(
            DELETE_REPORT_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Check reports
    reports = (
        db_session
        .query(ReportsTable)
        .order_by(ReportsTable.filename)
        .all()
    )
    assert len(reports) == 2
    assert reports[0].is_deleted is True
    assert reports[0].deleted_at == ApproxDatetime(utc_now())
    assert reports[1].is_deleted is False

    # Check report rows
    rows = db_session.query(ReportRowsTable).all()
    assert len(rows) == 1
    assert rows[0].name == "nnn"


def test_delete_report_when_already_deleted(
    client: TestClient,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    report = make_db_report(
        user_id=user_id,
        is_deleted=True,
        deleted_at=datetime(2021, 10, 17),
    )
    create_db_object(report)

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.delete(
            DELETE_REPORT_PATH.format(report_id=report.report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.NOT_FOUND

    # Check reports
    reports = db_session.query(ReportsTable).all()
    assert reports[0].is_deleted is True
    assert reports[0].deleted_at == datetime(2021, 10, 17)


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_delete_report_forbidden_when_not_authenticated(
    client: TestClient,
    headers: tp.Dict[str, str],
) -> None:
    with client:
        resp = client.delete(
            DELETE_REPORT_PATH.format(report_id=uuid4()),
            headers=headers,
        )
    assert_forbidden(resp)


def test_delete_report_forbidden_when_foreign_report(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    foreign_report_id = uuid4()
    foreign_report = make_db_report(
        foreign_report_id,
        user_id=uuid4(),
        parse_status=ParseStatus.parsed,
    )
    create_db_object(foreign_report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            DELETE_REPORT_PATH.format(report_id=foreign_report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert_forbidden(resp, "forbidden")


def test_delete_report_when_not_exist(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    with client:
        resp = client.get(
            DELETE_REPORT_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND
