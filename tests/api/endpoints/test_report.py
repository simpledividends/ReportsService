import os.path
from http import HTTPStatus
from tempfile import NamedTemporaryFile

import orjson
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import ReportsTable
from reports_service.models.report import ParseStatus
from reports_service.utils import utc_now
from tests.helpers import assert_all_tables_are_empty
from tests.utils import AnyUUID, ApproxDatetime

UPLOAD_REPORT_PATH = "/reports"


def test_upload_report_success(
    client: TestClient,
    db_session: orm.Session,
) -> None:
    now = utc_now()
    with NamedTemporaryFile("rb+") as f:
        filename = os.path.basename(f.name)
        f.write(b"some data")
        f.seek(0)
        with client:
            resp = client.post(
                UPLOAD_REPORT_PATH,
                files={"file": f},
                headers={"Authorization": "Bearer some_token"}
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
