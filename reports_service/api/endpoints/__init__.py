from fastapi import FastAPI

from .health import router as health_router
from .parsed import router as parsed_router
from .payment import router as payment_router
from .report import router as report_router


def add_routes(app: FastAPI) -> None:
    for router in (
        health_router,
        parsed_router,
        payment_router,
        report_router,
    ):
        app.include_router(router)
