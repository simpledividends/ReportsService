from asyncpg import create_pool
from fastapi import FastAPI

from .auth import AuthService
from .db.service import DBService
from .payment import PaymentService
from .pricing import PriceService
from .queue import QueueService
from .settings import ServiceConfig
from .storage import StorageService


def get_auth_service(app: FastAPI) -> AuthService:
    return app.state.auth_service


def get_db_service(app: FastAPI) -> DBService:
    return app.state.db_service


def get_queue_service(app: FastAPI) -> QueueService:
    return app.state.queue_service


def get_storage_service(app: FastAPI) -> StorageService:
    return app.state.storage_service


def get_price_service(app: FastAPI) -> PriceService:
    return app.state.price_service


def get_payment_service(app: FastAPI) -> PaymentService:
    return app.state.payment_service


def make_auth_service(config: ServiceConfig) -> AuthService:
    config_dict = config.auth_service_config.dict()
    request_id_header = config_dict.pop("auth_service_request_id_header")
    config_dict["request_id_header"] = request_id_header
    return AuthService(**config_dict)


def make_db_service(config: ServiceConfig) -> DBService:
    db_config = config.db_config.dict()
    pool_config = db_config.pop("db_pool_config")
    pool_config["dsn"] = pool_config.pop("db_url")
    pool = create_pool(**pool_config)
    service = DBService(pool=pool, **db_config)
    return service


def make_queue_service(config: ServiceConfig) -> QueueService:
    return QueueService(**config.queue_config.dict())


def make_storage_service(config: ServiceConfig) -> StorageService:
    return StorageService(**config.storage_config.dict())


def make_price_service(config: ServiceConfig) -> PriceService:
    return PriceService(**config.price_config.dict())


def make_payment_service(config: ServiceConfig) -> PaymentService:
    return PaymentService(**config.payment_config.dict())
