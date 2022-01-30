
import typing as tp
from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import orm

from reports_service.db.models import PromocodesTable, ReportsTable
from reports_service.models.payment import PromocodeUsage
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
    make_promocode,
)
from tests.utils import AnyStr, AnyUUID, ApproxDatetime

GET_PRICE_PATH = "/reports/{report_id}/price"
CREATE_PAYMENT_PATH = "/reports/{report_id}/payment"
ACCEPT_YOOKASSA_WEBHOOK_PATH = "/yookassa/webhook"


def test_get_price_without_promocode(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    create_db_object: DBObjectCreator,
) -> None:
    user_id = uuid4()
    report = make_db_report(
        user_id=user_id,
        price=Decimal("156.32"),
    )
    report_id = report.report_id  # It don't do this sqlalchemy works incorrect
    create_db_object(report)
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.get(
            GET_PRICE_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "start_price": 156.32,
        "final_price": 156.32,
        "discount": 0,
        "promocode_usage": PromocodeUsage.not_set,
        "used_promocode": None,
    }


@pytest.mark.parametrize("promocode_type", ("common", "personal"))
def test_get_price_with_valid_promocode(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    create_db_object: DBObjectCreator,
    promocode_type: str,
) -> None:
    user_id = uuid4()
    report = make_db_report(
        user_id=user_id,
        price=Decimal("156.32"),
    )
    report_id = report.report_id  # It don't do this sqlalchemy works incorrect
    create_db_object(report)

    promocode_user_id = user_id if promocode_type == "personal" else None
    promocode = make_promocode(user_id=promocode_user_id, discount=15)
    create_db_object(promocode)

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.get(
            GET_PRICE_PATH.format(report_id=report_id),
            params={"promo": "promo123"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "start_price": 156.32,
        "final_price": 132.87,
        "discount": 15,
        "promocode_usage": PromocodeUsage.success,
        "used_promocode": promocode.promocode,
    }


@pytest.mark.parametrize("expired_type", ("before", "after"))
@pytest.mark.parametrize("promocode_type", ("common", "personal"))
def test_get_price_with_expired_promocode(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    create_db_object: DBObjectCreator,
    expired_type: str,
    promocode_type: str,
) -> None:
    user_id = uuid4()
    report = make_db_report(
        user_id=user_id,
        price=Decimal("156.32"),
    )
    report_id = report.report_id  # It don't do this sqlalchemy works incorrect
    create_db_object(report)

    promocode_user_id = user_id if promocode_type == "personal" else None
    if expired_type == "before":
        params = {"valid_from": utc_now() + timedelta(days=1)}
    else:  # after
        params = {"valid_to": utc_now() - timedelta(days=1)}
    create_db_object(
        make_promocode(user_id=promocode_user_id, **params)  # type: ignore
    )

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.get(
            GET_PRICE_PATH.format(report_id=report_id),
            params={"promo": "promo123"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "start_price": 156.32,
        "final_price": 156.32,
        "discount": 0,
        "promocode_usage": PromocodeUsage.expired,
        "used_promocode": None,
    }


@pytest.mark.parametrize(
    "promocode_params",
    (
        {"rest_usages": 0},
        {"rest_usages": -1},
        {"user_id": uuid4()},
        {"promo_code": "OTHERCODE"}
    ),
)
def test_get_price_with_non_existent_promocode(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    create_db_object: DBObjectCreator,
    promocode_params: tp.Dict[str, tp.Any],
) -> None:
    user_id = uuid4()
    report = make_db_report(
        user_id=user_id,
        price=Decimal("156.32"),
    )
    report_id = report.report_id  # It don't do this sqlalchemy works incorrect
    create_db_object(report)

    create_db_object(make_promocode(**promocode_params))

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.get(
            GET_PRICE_PATH.format(report_id=report_id),
            params={"promo": "promo123"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "start_price": 156.32,
        "final_price": 156.32,
        "discount": 0,
        "promocode_usage": PromocodeUsage.not_exist,
        "used_promocode": None,
    }


@pytest.mark.parametrize("headers", ({}, {"Authorization": "Bearer token"}))
def test_get_price_not_authenticated(
    client: TestClient,
    headers: tp.Dict[str, str],
) -> None:
    with client:
        resp = client.get(
            GET_PRICE_PATH.format(report_id=uuid4()),
            headers=headers,
        )
    assert_forbidden(resp)


def test_get_price_of_foreign_report(
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
        resp = client.get(
            GET_PRICE_PATH.format(report_id=foreign_report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert_forbidden(resp, "forbidden")


def test_get_price_of_non_existent_report(
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
        resp = client.get(
            GET_PRICE_PATH.format(report_id=uuid4()),
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_get_price_when_price_is_null(
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
            price=None,
        )
    )
    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.get(
            GET_PRICE_PATH.format(report_id=report_id),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "payment_status",
    (PaymentStatus.not_payed, PaymentStatus.error, PaymentStatus.in_progress),
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

    # Check request to yookassa
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
        "description":
            f"Оплата отчета {report.broker} от {report.created_at} UTC",
        "receipt": {
            "customer": {
                "email": "user@ma.il",
            },
            "items": [
                {
                    "description": "Плата за обработку отчета",
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
            "promocode": None,
            "token": AnyStr(),
        },
    }
    token = payment_request.json["metadata"]["token"]
    decoded_token = jwt.decode(
        token,
        payment_config.jwt_key,
        [payment_config.jwt_algorithm],
    )
    assert decoded_token == {"id": AnyUUID()}


@pytest.mark.parametrize("promocode_type", ("common", "personal"))
@pytest.mark.parametrize(
    "payment_status",
    (PaymentStatus.not_payed, PaymentStatus.error, PaymentStatus.in_progress),
)
def test_create_payment_success_with_valid_promocode(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    fake_payment_server: FakePaymentServer,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    promocode_type: str,
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

    promocode_user_id = user_id if promocode_type == "personal" else None
    create_db_object(make_promocode(user_id=promocode_user_id, discount=15))

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=report_id),
            params={"promo": "promo123"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # Check response
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json() == {"confirmation_url": CONFIRMATION_URL}

    # Check promocode rest usages decremented
    promocode = db_session.query(PromocodesTable).first()
    assert promocode.rest_usages == 999

    # Check request to yookassa
    payment_request = fake_payment_server.requests[0]
    payment_config = service_config.payment_config
    assert payment_request.json == {
        "amount": {
            "value": "132.87",
            "currency": "RUB",
        },
        "description":
            f"Оплата отчета {report.broker} от {report.created_at} UTC",
        "receipt": {
            "customer": {
                "email": "user@ma.il",
            },
            "items": [
                {
                    "description": "Плата за обработку отчета",
                    "quantity": "1",
                    "amount": {
                        "value": "132.87",
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
            "request_id": "-",
            "promocode": "PROMO123",
            "token": AnyStr(),
        },
    }


@pytest.mark.parametrize(
    "promocode_params",
    (
        {"rest_usages": 0},
        {"rest_usages": -1},
        {"user_id": uuid4()},
        {"promo_code": "OTHERCODE"},
        {"valid_from": utc_now() + timedelta(days=1)},
        {"valid_to": utc_now() - timedelta(days=1)},
    ),
)
@pytest.mark.parametrize(
    "payment_status",
    (PaymentStatus.not_payed, PaymentStatus.error, PaymentStatus.in_progress),
)
def test_create_payment_success_with_invalid_promocode(
    client: TestClient,
    fake_auth_server: FakeAuthServer,
    fake_payment_server: FakePaymentServer,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    promocode_params: tp.Dict[str, tp.Any],
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

    created_promocode = make_promocode(**promocode_params)
    create_db_object(created_promocode)

    access_token = "some_token"
    fake_auth_server.add_ok_response(access_token, user_id)

    with client:
        resp = client.post(
            CREATE_PAYMENT_PATH.format(report_id=report_id),
            params={"promo": "promo123"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # Check response
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json() == {"confirmation_url": CONFIRMATION_URL}

    # Check promocode rest usages decremented
    promocode = db_session.query(PromocodesTable).first()
    assert promocode.rest_usages == created_promocode.rest_usages

    # Check request to yookassa
    payment_request = fake_payment_server.requests[0]
    payment_config = service_config.payment_config
    assert payment_request.json == {
        "amount": {
            "value": str(report.price),
            "currency": "RUB",
        },
        "description":
            f"Оплата отчета {report.broker} от {report.created_at} UTC",
        "receipt": {
            "customer": {
                "email": "user@ma.il",
            },
            "items": [
                {
                    "description": "Плата за обработку отчета",
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
            "request_id": "-",
            "promocode": None,
            "token": AnyStr(),
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

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == "no_price"


@pytest.mark.parametrize(
    "event,cancellation_reason,expected_payment_status",
    (
        ("payment.succeeded", None, PaymentStatus.payed),
        (
            "payment.canceled",
            "expired_on_confirmation",
            PaymentStatus.not_payed,
        ),
        ("payment.canceled", "card_expired", PaymentStatus.error),
    ),
)
def test_accept_yookassa_webhook_success(
    client: TestClient,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    event: str,
    cancellation_reason: tp.Optional[str],
    expected_payment_status: PaymentStatus,
) -> None:
    report_id = uuid4()
    create_db_object(make_db_report(report_id))
    body = {
        "type": "notification",
        "event": event,
        "object": {
            "id": str(uuid4()),
            "metadata": {
                "report_id": str(report_id),
                "token": jwt.encode(
                    {},
                    service_config.payment_config.jwt_key,
                    service_config.payment_config.jwt_algorithm,
                )
            },
            "cancellation_details": {
                "reason": cancellation_reason,
            }
        }
    }
    with client:
        resp = client.post(
            ACCEPT_YOOKASSA_WEBHOOK_PATH,
            json=body,
        )

    assert resp.status_code == HTTPStatus.OK

    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].payment_status == expected_payment_status


@pytest.mark.parametrize(
    "event,cancellation_reason,expected_payment_status,expected_rest_usages",
    (
        ("payment.succeeded", None, PaymentStatus.payed, 1000),
        (
            "payment.canceled",
            "expired_on_confirmation",
            PaymentStatus.not_payed,
            1000,
        ),
        ("payment.canceled", "card_expired", PaymentStatus.error, 1001),
    ),
)
def test_accept_yookassa_webhook_success_with_promocode(
    client: TestClient,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    event: str,
    cancellation_reason: tp.Optional[str],
    expected_payment_status: PaymentStatus,
    expected_rest_usages: int,
) -> None:
    report_id = uuid4()
    create_db_object(make_db_report(report_id))
    create_db_object(make_promocode(rest_usages=1000))
    body = {
        "type": "notification",
        "event": event,
        "object": {
            "id": str(uuid4()),
            "metadata": {
                "report_id": str(report_id),
                "promocode": "PROMO123",
                "token": jwt.encode(
                    {},
                    service_config.payment_config.jwt_key,
                    service_config.payment_config.jwt_algorithm,
                )
            },
            "cancellation_details": {
                "reason": cancellation_reason,
            }
        }
    }
    with client:
        resp = client.post(
            ACCEPT_YOOKASSA_WEBHOOK_PATH,
            json=body,
        )

    assert resp.status_code == HTTPStatus.OK

    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].payment_status == expected_payment_status

    promocode = db_session.query(PromocodesTable).first()
    assert promocode.rest_usages == expected_rest_usages


def test_accept_yookassa_webhook_error_when_token_incorrect(
    client: TestClient,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
) -> None:
    report_id = uuid4()
    create_db_object(make_db_report(report_id))
    body = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": str(uuid4()),
            "metadata": {
                "report_id": str(report_id),
                "token": jwt.encode(
                    {},
                    service_config.payment_config.jwt_key + "a",
                    service_config.payment_config.jwt_algorithm,
                )
            },
        }
    }
    with client:
        resp = client.post(
            ACCEPT_YOOKASSA_WEBHOOK_PATH,
            json=body,
        )

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].payment_status == PaymentStatus.not_payed


@pytest.mark.parametrize(
    "event",
    ("payment.waiting_for_capture", "refund.succeeded"),
)
def test_accept_yookassa_webhook_error_when_unexpected_event(
    client: TestClient,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    event: str,
) -> None:
    report_id = uuid4()
    create_db_object(make_db_report(report_id))
    body = {
        "type": "notification",
        "event": event,
        "object": {
            "id": str(uuid4()),
            "metadata": {
                "report_id": str(report_id),
                "token": jwt.encode(
                    {},
                    service_config.payment_config.jwt_key,
                    service_config.payment_config.jwt_algorithm,
                )
            },
        }
    }
    with client:
        resp = client.post(
            ACCEPT_YOOKASSA_WEBHOOK_PATH,
            json=body,
        )

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].payment_status == PaymentStatus.not_payed


def test_accept_yookassa_webhook_error_when_report_not_exist(
    client: TestClient,
    db_session: orm.Session,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
) -> None:
    report_id = uuid4()
    create_db_object(make_db_report(uuid4()))  # other report
    body = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": str(uuid4()),
            "metadata": {
                "report_id": str(report_id),
                "token": jwt.encode(
                    {},
                    service_config.payment_config.jwt_key,
                    service_config.payment_config.jwt_algorithm,
                )
            },
        }
    }
    with client:
        resp = client.post(
            ACCEPT_YOOKASSA_WEBHOOK_PATH,
            json=body,
        )

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    reports = db_session.query(ReportsTable).all()
    assert len(reports) == 1
    assert reports[0].payment_status == PaymentStatus.not_payed
