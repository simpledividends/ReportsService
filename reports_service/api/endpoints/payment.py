
import typing as tp
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from reports_service.api import responses
from reports_service.api.auth import get_request_user
from reports_service.api.exceptions import (
    AppException,
    ForbiddenException,
    NotFoundException,
    NotParsedException,
)
from reports_service.db.service import DBService
from reports_service.log import app_logger
from reports_service.models.payment import (
    Price,
    YookassaEvent,
    YookassaEventBody,
)
from reports_service.models.report import ParseStatus, PaymentStatus, Report
from reports_service.models.user import User
from reports_service.pricing import PriceService
from reports_service.response import create_response
from reports_service.services import (
    get_db_service,
    get_payment_service,
    get_price_service,
)

router = APIRouter()

USER_PAYMENT_CANCELLATION_REASONS = ("expired_on_confirmation",)


async def _get_report_price(
    report: Report,
    promo: tp.Optional[str],
    db_service: DBService,
    price_service: PriceService,
) -> Price:
    promocode_not_exist = False
    promocode = None
    if promo is not None:
        promo = promo.upper()
        promocode = await db_service.get_promocode(promo)
        if promocode is None:
            promocode_not_exist = True
    price = price_service.get_price(report, promocode, promocode_not_exist)
    return price


@router.get(
    path="/reports/{report_id}/price",
    tags=["Payment"],
    status_code=HTTPStatus.OK,
    response_model=Price,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
        409: responses.no_price,
    }
)
async def get_report_price(
    request: Request,
    report_id: UUID,
    promo: tp.Optional[str] = Query(None),
    user: User = Depends(get_request_user)
) -> Price:
    app_logger.info(
        f"User {user.user_id} requests price for report {report_id}"
        f" with promocode {promo}"
    )

    db_service = get_db_service(request.app)
    report = await db_service.get_report(report_id)
    app_logger.info("Got report (or nothing) from db")

    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()
    if report.price is None:
        raise AppException(
            status_code=HTTPStatus.CONFLICT,
            error_key="no_price",
            error_message="Price not set for this report (yet)",
        )

    price = await _get_report_price(
        report=report,
        promo=promo,
        db_service=db_service,
        price_service=get_price_service(request.app),
    )

    app_logger.info(f"Got price: {price}")

    return price


class CreatedPayment(BaseModel):
    confirmation_url: str


@router.post(
    path="/reports/{report_id}/payment",
    tags=["Payment"],
    status_code=HTTPStatus.CREATED,
    response_model=CreatedPayment,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
        409: responses.not_parsed_or_payed_or_no_price,
    }
)
async def create_payment(
    request: Request,
    report_id: UUID,
    promo: tp.Optional[str] = Query(None),
    user: User = Depends(get_request_user)
) -> CreatedPayment:
    app_logger.info(
        f"User {user.user_id} pay for report {report_id}"
        f" with promocode {promo}"
    )

    db_service = get_db_service(request.app)
    report = await db_service.get_report(report_id)
    app_logger.info("Got report (or nothing) from db")

    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()
    if report.parse_status != ParseStatus.parsed:
        raise NotParsedException()
    if report.price is None:
        raise AppException(
            status_code=HTTPStatus.CONFLICT,
            error_key="no_price",
            error_message="Price not set for this report (yet)",
        )
    if report.payment_status == PaymentStatus.payed:
        raise AppException(
            status_code=HTTPStatus.CONFLICT,
            error_key="report_already_payed",
            error_message="Report is already payed",
        )
    if report.payment_status == PaymentStatus.in_progress:
        raise AppException(
            status_code=HTTPStatus.CONFLICT,
            error_key="report_payment_in_progress",
            error_message="Report payment in progress",
        )

    price = await _get_report_price(
        report=report,
        promo=promo,
        db_service=db_service,
        price_service=get_price_service(request.app),
    )

    payment_service = get_payment_service(request.app)
    confirmation_url, body = await payment_service.create_payment(
        user,
        report,
        price,
    )

    metadata = body["metadata"]
    metadata.pop("token")
    app_logger.info(
        f"Payment created. Confirmation_url: {confirmation_url}."
        f" Metadata: {metadata}"
    )

    await db_service.update_payment_status(
        report_id,
        PaymentStatus.in_progress,
    )
    app_logger.info("Updated payment status")

    if body["metadata"]["promocode"] is not None:
        await db_service.update_promocode_rest_usages(
            body["metadata"]["promocode"],
            -1
        )
        app_logger.info("Promocode rest usages decremented.")

    return CreatedPayment(confirmation_url=confirmation_url)


@router.post(
    path="/yookassa/webhook",
    tags=["Payment"],
    status_code=HTTPStatus.OK,
)
async def accept_yookassa_webhook(
    request: Request,
    body: YookassaEventBody,
) -> JSONResponse:
    payment_service = get_payment_service(request.app)
    payment_service.verify_authenticity_of_webhook(body)

    event = body.event
    metadata = body.object["metadata"]
    metadata.pop("token")
    app_logger.info(
        f"Received {event} webhook. Yookassa payment id: {body.object['id']}."
        f" Metadata: {metadata}."
    )

    if event == YookassaEvent.succeeded:
        payment_status = PaymentStatus.payed
    elif event == YookassaEvent.cancelled:
        cancellation_details = body.object["cancellation_details"]
        app_logger.info(f"Cancellation_details: {cancellation_details}")
        if cancellation_details["reason"] in USER_PAYMENT_CANCELLATION_REASONS:
            payment_status = PaymentStatus.not_payed
        else:
            payment_status = PaymentStatus.error
    else:
        raise ValueError(f"Unexpected webhook event {event}")
    app_logger.info(f"Chosen payment status: {payment_status}")

    db_service = get_db_service(request.app)
    report_id = metadata["report_id"]

    report = await db_service.get_report(report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not exists")
    await db_service.update_payment_status(report_id, payment_status)
    app_logger.info("Payment status updated")

    if (
        metadata.get("promocode") is not None
        and payment_status == PaymentStatus.error
    ):
        await db_service.update_promocode_rest_usages(
            metadata["promocode"],
            +1
        )
        app_logger.info("Promocode rest usages incremented.")

    return create_response(status_code=HTTPStatus.OK)
