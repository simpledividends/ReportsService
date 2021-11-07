import asyncio
import typing as tp
from concurrent.futures.thread import ThreadPoolExecutor

import uvloop
from fastapi import FastAPI

from ..log import app_logger, setup_logging
from ..services import (
    make_auth_service,
    make_payment_service,
    make_price_service,
    make_queue_service,
    make_storage_service,
)
from ..settings import ServiceConfig
from .endpoints import add_routes
from .events import add_events
from .exception_handlers import add_exception_handlers
from .middlewares import add_middlewares

__all__ = ("create_app",)


def setup_asyncio(thread_name_prefix: str) -> None:
    uvloop.install()

    loop = asyncio.get_event_loop()

    executor = ThreadPoolExecutor(thread_name_prefix=thread_name_prefix)
    loop.set_default_executor(executor)

    def handler(_, context: tp.Dict[str, tp.Any]) -> None:
        message = "Caught asyncio exception: {message}".format_map(context)
        app_logger.warning(message)

    loop.set_exception_handler(handler)


def create_app(config: ServiceConfig) -> FastAPI:
    setup_logging(config)
    setup_asyncio(thread_name_prefix=config.service_name)

    app = FastAPI(debug=False)

    app.state.max_report_size = config.max_report_size
    app.state.auth_service = make_auth_service(config)
    app.state.queue_service = make_queue_service(config)
    app.state.storage_service = make_storage_service(config)
    app.state.price_service = make_price_service(config)
    app.state.payment_service = make_payment_service(config)

    add_routes(app)
    add_middlewares(app, config.request_id_header)
    add_exception_handlers(app)
    add_events(app, config)

    return app
