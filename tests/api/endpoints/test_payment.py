
import typing as tp
from decimal import Decimal
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import ReportsTable
from reports_service.models.report import ParseStatus, PaymentStatus
from reports_service.settings import ServiceConfig
from reports_service.utils import utc_now
from tests.helpers import (
    CONFIRMATION_URL,
    DBObjectCreator,
    FakeAuthServer,
    FakePaymentServer,
    assert_forbidden,
    make_db_report,
)
from tests.utils import ApproxDatetime

CREATE_PAYMENT_PATH = "/reports/{report_id}/payment"


@pytest.mark.parametrize(
    "payment_status",
    (PaymentStatus.not_payed, PaymentStatus.error),
)
def test_create_payment_success(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    fake_payment_server: FakePaymentServer,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    payment_status: PaymentStatus,
) -> None:
    user_id = uuid4()
    report = make_db_report(
        user_id=user_id,
        parse_status=ParseStatus.parsed,
        payment_status=payment_status,
        price=Decimal("156.32"),
        broker="broker",
    )
    report_id = report.report_id  # It don't do this sqlalchemy works incorrect
    create_db_object(report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)
    request_id = "some_request_id"

    now = utc_now()
    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=report_id),
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Request-Id": request_id,
            },
        )

    # Check response
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json() == {"confirmation_url": CONFIRMATION_URL}

    # Check payment status updated
    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].payment_status == PaymentStatus.in_progress
    assert reports[0].payment_status_updated_at == ApproxDatetime(now)

    # Check request to yoomoney
    assert len(fake_payment_server.requests) == 1
    payment_request = fake_payment_server.requests[0]
    payment_config = service_config.payment_config
    assert payment_request.authorization == {
        "username": payment_config.shop_id,
        "password": payment_config.secret_key,
    }
    assert UUID(payment_request.headers["Idempotence-Key"])
    assert payment_request.json == {
        "amount": {
            "value": str(report.price),
            "currency": "RUB",
        },
        "description": f"Оплата отчета {report.broker} от {report.created_at}",
        "receipt": {
            "customer": {
                "email": "user@ma.il",
            },
            "items": [
                {
                    "description": f"Отчет {report.report_id}",
                    "quantity": "1",
                    "amount": {
                        "value": str(report.price),
                        "currency": "RUB",
                    },
                    "vat_code": payment_config.vat_code,
                    "payment_subject": payment_config.payment_subject,
                    "payment_mode": payment_config.payment_mode,
                    "product_code": payment_config.product_code,
                },
            ],
        },
        "confirmation": {
            "type": "redirect",
            "locale": "ru_RU",
            "return_url": payment_config.return_url,
        },
        "capture": True,
        "metadata": {
            "user_id": str(user_id),
            "report_id": str(report_id),
            "request_id": request_id,
        },
    }


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_create_payment_not_authenticated(
    client: TestClient,
    headers: tp.Dict[str, str],
) -> None:
    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=uuid4()),
            headers=headers,
        )
    assert_forbidden(resp)


def test_create_payment_foreign_report(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    foreign_report_id = uuid4()
    foreign_report = make_db_report(
        foreign_report_id,
        user_id=uuid4(),
    )
    create_db_object(foreign_report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=foreign_report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert_forbidden(resp, "forbidden")


def test_create_payment_report_not_exist(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    other_report = make_db_report(user_id=uuid4())
    create_db_object(other_report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=uuid4()),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "parse_status",
    (ParseStatus.in_progress, ParseStatus.not_parsed),
)
def test_create_payment_report_not_parsed(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    parse_status: ParseStatus,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    create_db_object(
        make_db_report(
            report_id=report_id,
            user_id=user_id,
            parse_status=parse_status,
            payment_status=PaymentStatus.not_payed,
            price=Decimal("156.32"),
        )
    )
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == "report_not_parsed"


@pytest.mark.parametrize(
    "payment_status,error_key",
    (
        (PaymentStatus.payed, "report_already_payed"),
        (PaymentStatus.in_progress, "report_payment_in_progress"),
    )
)
def test_create_payment_for_already_payed_report(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
    payment_status: PaymentStatus,
    error_key: str,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    create_db_object(
        make_db_report(
            report_id=report_id,
            user_id=user_id,
            parse_status=ParseStatus.parsed,
            payment_status=payment_status,
            price=Decimal("156.32"),
        )
    )
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == error_key


def test_create_payment_price_is_null(
    client: TestClient,
    create_db_object: DBObjectCreator,
    fake_auth_server: FakeAuthServer,
) -> None:
    user_id = uuid4()
    report_id = uuid4()
    create_db_object(
        make_db_report(
            report_id=report_id,
            user_id=user_id,
            parse_status=ParseStatus.parsed,
            payment_status=PaymentStatus.not_payed,
            price=None,
        )
    )
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
