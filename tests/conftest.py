# pylint: disable=redefined-outer-name
import os
import typing as tp
from contextlib import contextmanager
from pathlib import Path

import boto3
import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic import config as alembic_config
from botocore.client import BaseClient
from fastapi import FastAPI
from sqlalchemy import orm
from starlette.testclient import TestClient

from reports_service.api.app import create_app
from reports_service.settings import ServiceConfig, get_config
from tests.helpers import clear_bucket

CURRENT_DIR = Path(__file__).parent
ALEMBIC_INI_PATH = CURRENT_DIR.parent / "alembic.ini"


@contextmanager
def sqlalchemy_bind_context(url: str) -> tp.Iterator[sa.engine.Engine]:
    bind = sa.engine.create_engine(url)
    try:
        yield bind
    finally:
        bind.dispose()


@contextmanager
def sqlalchemy_session_context(
    bind: sa.engine.Engine,
) -> tp.Iterator[orm.Session]:
    session_factory = orm.sessionmaker(bind)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def migrations_context(alembic_ini: Path) -> tp.Iterator[None]:
    cfg = alembic_config.Config(alembic_ini)

    alembic_command.upgrade(cfg, "head")
    try:
        yield
    finally:
        alembic_command.downgrade(cfg, "base")


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.getenv("DB_URL")


@pytest.fixture(scope="session")
def db_bind(db_url: str) -> tp.Iterator[sa.engine.Engine]:
    with sqlalchemy_bind_context(db_url) as bind:
        yield bind


@pytest.fixture
def db_session(db_bind: sa.engine.Engine) -> tp.Iterator[orm.Session]:
    with migrations_context(ALEMBIC_INI_PATH):
        with sqlalchemy_session_context(db_bind) as session:
            yield session


@pytest.fixture
def service_config() -> ServiceConfig:
    return get_config()


@pytest.fixture
def s3_client(service_config: ServiceConfig) -> BaseClient:
    config = service_config.storage_config
    client = boto3.client(
        service_name="s3",
        endpoint_url=config.endpoint_url,
        region_name=config.region,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )
    return client


@pytest.fixture
def s3_bucket(
    s3_client: BaseClient,
    service_config: ServiceConfig,
) -> tp.Iterator[None]:
    bucket = service_config.storage_config.bucket
    s3_client.create_bucket(Bucket=bucket)

    yield

    clear_bucket(s3_client, bucket)


@pytest.fixture
def app(
    service_config: ServiceConfig,
    db_session: orm.Session,
    s3_bucket: None,
) -> FastAPI:
    app = create_app(service_config)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app=app)
