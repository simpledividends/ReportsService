from fastapi import FastAPI

from reports_service.log import app_logger
from reports_service.settings import ServiceConfig


def add_events(app: FastAPI, _: ServiceConfig) -> None:
    async def startup_event() -> None:
        app_logger.info("Startup")

    async def shutdown_event() -> None:
        app_logger.info("Shutdown")

    app.add_event_handler("startup", startup_event)
    app.add_event_handler("shutdown", shutdown_event)
