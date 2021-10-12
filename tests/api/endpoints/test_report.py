import base64
import os.path
import typing as tp
from http import HTTPStatus
from tempfile import NamedTemporaryFile
from uuid import uuid4

import orjson
import pytest
from botocore.client import BaseClient
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import ReportsTable
from reports_service.models.report import ParseStatus
from reports_service.settings import ServiceConfig
from reports_service.utils import utc_now
from tests.helpers import (
    DBObjectCreator,
    FakeAuthServer,
    assert_all_tables_are_empty,
    assert_forbidden,
    make_db_report,
)
from tests.utils import AnyUUID, ApproxDatetime

UPLOAD_REPORT_PATH = "/reports"
GET_REPORTS_PATH = "/reports"


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
    fake_auth_server.set_ok_responses({access_token: user_id})

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
        "broker": None,
        "year": None,
    }

    # Check DB content
    assert_all_tables_are_empty(db_session, [ReportsTable])
    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    report = reports[0]
    report_dict = orjson.loads(
        orjson.dumps({k: getattr(report, k) for k in resp_json.keys()})
    )
    assert report_dict == resp_json

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

    access_token = "some_token"
    fake_auth_server.set_ok_responses({access_token: user_1_id})

    with client:
        resp = client.get(
            GET_REPORTS_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    reports = resp.json()["reports"]
    report_names = [r["filename"] for r in reports]
    assert sorted(report_names) == ["report_1", "report_3"]


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
