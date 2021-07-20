from fastapi import FastAPI

from .health import router as health_router
from .report import router as report_router


def add_routes(app: FastAPI) -> None:
    for router in (
        health_router,
        report_router,
    ):
        app.include_router(router)
