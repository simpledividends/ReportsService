import time

from fastapi import FastAPI, Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from reports_service.context import REQUEST_ID
from reports_service.log import access_logger, app_logger
from reports_service.models.common import Error
from reports_service.response import server_error


class AccessMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        request_time = time.perf_counter() - started_at

        status_code = response.status_code

        access_logger.info(
            msg="",
            extra={
                "request_time": round(request_time, 4),
                "status_code": status_code,
                "requested_url": request.url,
                "method": request.method,
            },
        )
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, request_id_header: str):
        self.request_id_header = request_id_header
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(self.request_id_header, "-")
        token = REQUEST_ID.set(request_id)
        response = await call_next(request)
        if request_id != "-":
            response.headers[self.request_id_header] = request_id
        REQUEST_ID.reset(token)
        return response


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as e:  # pylint: disable=W0703,W1203
            app_logger.exception(
                msg=f"Caught unhandled {e.__class__} exception: {e}"
            )
            error = Error(
                error_key="server_error",
                error_message="Internal Server Error"
            )
            return server_error([error])


def add_middlewares(app: FastAPI, request_id_header: str) -> None:
    # do not change order
    app.add_middleware(ExceptionHandlerMiddleware)
    app.add_middleware(AccessMiddleware)
    app.add_middleware(
        RequestIdMiddleware,
        request_id_header=request_id_header,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
