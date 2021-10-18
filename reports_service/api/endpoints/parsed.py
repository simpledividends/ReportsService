import asyncio
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from reports_service.api import responses
from reports_service.api.auth import get_request_user, get_service_user
from reports_service.api.exceptions import (
    ForbiddenException,
    NotFoundException,
    NotParsedException,
    NotPayedException,
)
from reports_service.log import app_logger
from reports_service.models.report import (
    DetailedReportRows,
    ExtendedParsedReportInfo,
    ParseStatus,
    ParsingResult,
    PaymentStatus,
    SimpleReportRows,
)
from reports_service.models.user import User
from reports_service.response import create_response
from reports_service.services import get_db_service

router = APIRouter()


@router.put(
    path="/reports/{report_id}/parsed",
    tags=["Parsed"],
    status_code=HTTPStatus.CREATED,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
        422: responses.unprocessable_entity,
    }
)
async def upload_parsing_result(
    request: Request,
    report_id: UUID,
    parsing_result: ParsingResult,
    user: User = Depends(get_service_user)
) -> JSONResponse:
    app_logger.info(
        f"Service {user.user_id} sent parsing result for report {report_id}."
        f" Is parsed: {parsing_result.is_parsed},"
        f" message: {parsing_result.message}"
    )

    db_service = get_db_service(request.app)

    report = await db_service.get_report(report_id)
    if report is None:
        raise NotFoundException()

    await db_service.delete_report_rows(report_id)
    app_logger.info("Old rows deleted")

    if parsing_result.is_parsed and parsing_result.parsed_report is not None:
        parse_status = ParseStatus.parsed
        parsed_report = parsing_result.parsed_report
        rows = parsed_report.rows
        parsed_dict = parsed_report.dict()
        parsed_dict.pop("rows")
        if parsed_dict["period"][0].year == parsed_dict["period"][1].year:
            year = parsed_dict["period"][0].year
        else:
            year = None
        info = ExtendedParsedReportInfo(year=year, **parsed_dict)
        await asyncio.gather(
            db_service.update_parsed_report(report_id, parse_status, info),
            db_service.add_report_rows(report_id, rows)
        )
    else:
        await db_service.update_parsed_report(
            report_id,
            ParseStatus.not_parsed,
            None,
        )

    app_logger.info("Parsing result saved in db")

    return create_response(status_code=HTTPStatus.OK)


@router.get(
    path="/reports/{report_id}/rows",
    tags=["Report"],
    status_code=HTTPStatus.OK,
    response_model=SimpleReportRows,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
        409: responses.not_parsed,
    },
)
async def get_report_rows(
    request: Request,
    report_id: UUID,
    user: User = Depends(get_request_user)
) -> SimpleReportRows:
    app_logger.info(f"User {user.user_id} requested report {report_id} rows")

    db_service = get_db_service(request.app)

    report = await db_service.get_report(report_id)
    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()
    if report.parse_status != ParseStatus.parsed:
        raise NotParsedException()

    rows = await db_service.get_report_rows(report_id)
    return SimpleReportRows(rows=rows)


@router.get(
    path="/reports/{report_id}/rows/detailed",
    tags=["Report"],
    status_code=HTTPStatus.OK,
    response_model=DetailedReportRows,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
        409: responses.not_parsed,
        402: responses.not_payed,
    },
)
async def get_report_detailed_rows(
    request: Request,
    report_id: UUID,
    user: User = Depends(get_request_user)
) -> DetailedReportRows:
    app_logger.info(f"User {user.user_id} requested report {report_id} rows")

    db_service = get_db_service(request.app)

    report = await db_service.get_report(report_id)
    if report is None:
        raise NotFoundException()
    if report.user_id != user.user_id:
        raise ForbiddenException()
    if report.parse_status != ParseStatus.parsed:
        raise NotParsedException()
    if report.payment_status != PaymentStatus.payed:
        raise NotPayedException()

    rows = await db_service.get_report_detailed_rows(report_id)
    return DetailedReportRows(rows=rows)
