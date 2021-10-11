import base64
import os.path
from http import HTTPStatus
from tempfile import NamedTemporaryFile
from uuid import uuid4

import orjson
from botocore.client import BaseClient
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import ReportsTable
from reports_service.models.report import ParseStatus
from reports_service.settings import ServiceConfig
from reports_service.utils import utc_now
from tests.helpers import DBObjectCreator, assert_all_tables_are_empty, make_db_report
from tests.utils import AnyUUID, ApproxDatetime

UPLOAD_REPORT_PATH = "/reports"
GET_REPORTS_PATH = "/reports"


def test_upload_report_success(
    client: TestClient,
    db_session: orm.Session,
    s3_client: BaseClient,
    sqs_client: BaseClient,
    service_config: ServiceConfig,
    sqs_queue_url: str,
) -> None:
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
                    "Authorization": "Bearer some_token",
                    service_config.request_id_header: request_id,
                }
            )

    # Check response
    assert resp.status_code == HTTPStatus.CREATED
    resp_json = resp.json()
    assert resp_json == {
        "report_id": AnyUUID(),
        "user_id": AnyUUID(),
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
    assert msg_body_kwargs == {"storage_key": key, "request_id": request_id}


def test_get_reports_success(
    client: TestClient,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
) -> None:
    user_1_id = uuid4()
    user_2_id = uuid4()
    create_db_object(make_db_report(user_id=user_1_id, filename="report_1"))
    create_db_object(make_db_report(user_id=user_2_id, filename="report_2"))
    create_db_object(make_db_report(user_id=user_1_id, filename="report_3"))

    with client:
        resp = client.get(
            GET_REPORTS_PATH,
            headers={"Authorization": "Bearer some_token"},
        )

    assert resp.status_code == HTTPStatus.OK
    reports = resp.json()["reports"]
    report_names = [r["name"] for r in reports]
    assert sorted(report_names) == ["report_1", "report_3"]
