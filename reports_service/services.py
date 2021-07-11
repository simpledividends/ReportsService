from asyncpg import create_pool
from fastapi import FastAPI

from reports_service.db.service import DBService
from reports_service.settings import ServiceConfig


def get_db_service(app: FastAPI) -> DBService:
    return app.state.db_service


def make_db_service(config: ServiceConfig) -> DBService:
    db_config = config.db_config.dict()
    pool_config = db_config.pop("db_pool_config")
    pool_config["dsn"] = pool_config.pop("db_url")
    pool = create_pool(**pool_config)
    service = DBService(pool=pool, **db_config)
    return service
