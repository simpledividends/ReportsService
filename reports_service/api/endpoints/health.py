from http import HTTPStatus

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from reports_service.response import create_response

router = APIRouter()


@router.get(
    path="/ping",
    tags=["Health"],
)
async def ping(_: Request) -> JSONResponse:
    return create_response(message="pong", status_code=HTTPStatus.OK)


@router.get(
    path="/health",
    tags=["Health"],
)
async def health(request: Request) -> JSONResponse:
    return create_response(status_code=HTTPStatus.OK)
