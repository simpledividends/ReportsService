from asyncpg import create_pool
from fastapi import FastAPI

from reports_service.auth import AuthService
from reports_service.db.service import DBService
from reports_service.queue import QueueService
from reports_service.settings import ServiceConfig
from reports_service.storage import StorageService


def get_auth_service(app: FastAPI) -> AuthService:
    return app.state.auth_service


def get_db_service(app: FastAPI) -> DBService:
    return app.state.db_service


def get_queue_service(app: FastAPI) -> QueueService:
    return app.state.queue_service


def get_storage_service(app: FastAPI) -> StorageService:
    return app.state.storage_service


def make_auth_service(_: ServiceConfig) -> AuthService:
    return AuthService()


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
