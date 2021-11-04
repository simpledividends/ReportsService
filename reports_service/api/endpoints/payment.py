
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends
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
from reports_service.log import app_logger
from reports_service.models.payment import YookassaEvent, YookassaEventBody
from reports_service.models.report import ParseStatus, PaymentStatus
from reports_service.models.user import User
from reports_service.response import create_response
from reports_service.services import get_db_service, get_payment_service

router = APIRouter()

USER_PAYMENT_CANCELLATION_REASONS = ("expired_on_confirmation",)


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
        409: responses.not_parsed_or_payed,
    }
)
async def create_payment(
    request: Request,
    report_id: UUID,
    user: User = Depends(get_request_user)
) -> CreatedPayment:
    app_logger.info(f"User {user.user_id} pay for report {report_id}")

    db_service = get_db_service(request.app)
    report = await db_service.get_report(report_id)
    app_logger.info("Got report (or nothing) from db")

    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()
    if report.parse_status != ParseStatus.parsed:
        raise NotParsedException()
    if report.payment_status == PaymentStatus.payed:
        raise AppException(
            status_code=HTTPStatus.CONFLICT,
            error_key="report_already_payed",
            error_message="Report already payed",
        )
    if report.payment_status == PaymentStatus.in_progress:
        raise AppException(
            status_code=HTTPStatus.CONFLICT,
            error_key="report_payment_in_progress",
            error_message="Report payment in progress",
        )

    payment_service = get_payment_service(request.app)
    confirmation_url = await payment_service.create_payment(user, report)
    app_logger.info(f"Got confirmation_url: {confirmation_url}")

    await db_service.update_payment_status(
        report_id,
        PaymentStatus.in_progress,
    )
    app_logger.info("Updated payment status")

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
        if cancellation_details["reason"] in USER_PAYMENT_CANCELLATION_REASONS:
            payment_status = PaymentStatus.not_payed
        else:
            payment_status = PaymentStatus.error
    else:
        raise ValueError(f"Unexpected webhook event {event}")
    app_logger.info(f"Chosen payment status: {payment_status}")

    report_id = metadata["report_id"]
    db_service = get_db_service(request.app)
    report = await db_service.get_report(report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not exists")
    await db_service.update_payment_status(report_id, payment_status)
    app_logger.info("Payment status updated")

    return create_response(status_code=HTTPStatus.OK)
