from http import HTTPStatus

from fastapi import APIRouter, UploadFile, File, Security, Depends
from starlette.requests import Request
from starlette.responses import JSONResponse

from reports_service.api.auth import get_request_user
from reports_service.log import app_logger
from reports_service.models.report import Report
from reports_service.models.user import User
from reports_service.response import create_response
from reports_service.services import get_db_service, get_storage_service, \
    get_queue_service

router = APIRouter()


@router.post(
    path="/reports",
    tags=["Report"],
    status_code=HTTPStatus.CREATED,
    response_model=Report,
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
    await storage_service.save_report(report.report_id, file)
    app_logger.info(f"Report {report.report_id} saved to storage")

    queue_service = get_queue_service(request.app)
    await queue_service.send_parse_message(report.report_id)
    app_logger.info(f"Parse message for report {report.report_id} sent")

    return report
