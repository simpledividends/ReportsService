
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.requests import Request

from reports_service.api import responses
from reports_service.api.auth import get_request_user
from reports_service.api.exceptions import (
    AppException,
    ForbiddenException,
    NotFoundException,
    NotParsedException,
)
from reports_service.log import app_logger
from reports_service.models.report import ParseStatus, PaymentStatus
from reports_service.models.user import User
from reports_service.services import get_db_service, get_payment_service

router = APIRouter()


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
