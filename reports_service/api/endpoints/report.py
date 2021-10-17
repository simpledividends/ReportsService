from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from starlette.requests import Request

from reports_service.api import responses
from reports_service.api.auth import get_request_user
from reports_service.api.exceptions import (
    ForbiddenException,
    NotFoundException,
)
from reports_service.log import app_logger
from reports_service.models.report import Report, Reports
from reports_service.models.user import User
from reports_service.services import (
    get_db_service,
    get_queue_service,
    get_storage_service,
)

router = APIRouter()


@router.post(
    path="/reports",
    tags=["Report"],
    status_code=HTTPStatus.CREATED,
    response_model=Report,
    responses={
        403: responses.forbidden,
        422: responses.unprocessable_entity,
    }
)
async def upload_report(
    request: Request,
    file: UploadFile = File(..., description="Report file"),
    user: User = Depends(get_request_user)
) -> Report:
    app_logger.info(f"User {user.user_id} uploaded report {file.filename}")

    db_service = get_db_service(request.app)
    report = await db_service.add_new_report(user.user_id, file.filename)
    app_logger.info(f"Report {report.report_id} created in db")

    storage_service = get_storage_service(request.app)
    key = await storage_service.save_report(report.report_id, file)
    app_logger.info(f"Report {report.report_id} saved to storage")

    queue_service = get_queue_service(request.app)
    await queue_service.send_parse_message(report.report_id, key)
    app_logger.info(f"Parse message for report {report.report_id} sent")

    return report


@router.get(
    path="/reports",
    tags=["Report"],
    status_code=HTTPStatus.OK,
    response_model=Reports,
    responses={
        403: responses.forbidden,
    },
)
async def get_reports(
    request: Request,
    user: User = Depends(get_request_user)
) -> Reports:
    app_logger.info(f"User {user.user_id} requested reports")
    db_service = get_db_service(request.app)
    reports = await db_service.get_reports(user.user_id)
    return Reports(reports=reports)


@router.get(
    path="/reports/{report_id}",
    tags=["Report"],
    status_code=HTTPStatus.OK,
    response_model=Report,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
    },
)
async def get_report(
    request: Request,
    report_id: UUID,
    user: User = Depends(get_request_user)
) -> Report:
    app_logger.info(f"User {user.user_id} requested report {report_id}")

    db_service = get_db_service(request.app)

    report = await db_service.get_report(report_id)
    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()

    return report


@router.delete(
    path="/reports/{report_id}",
    tags=["Report"],
    status_code=HTTPStatus.NO_CONTENT,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
    },
)
async def delete_report(
    request: Request,
    report_id: UUID,
    user: User = Depends(get_request_user),
) -> None:
    app_logger.info(f"User {user.user_id} want to delete report {report_id}")

    db_service = get_db_service(request.app)

    report = await db_service.get_report(report_id)
    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()

    await db_service.delete_report_rows(report_id)
    await db_service.set_report_deleted(report_id)

    app_logger.info(f"Report {report_id} was deleted")
