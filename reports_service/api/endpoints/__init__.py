from fastapi import FastAPI

from .health import router as health_router


def add_routes(app: FastAPI) -> None:
    for router in (
        health_router,
    ):
        app.include_router(router)
