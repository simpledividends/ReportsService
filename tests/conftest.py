# pylint: disable=redefined-outer-name
import os
import typing as tp
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin

import boto3
import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from alembic import command as alembic_command
from alembic import config as alembic_config
from botocore.client import BaseClient
from fastapi import FastAPI
from pytest_httpserver import HTTPServer
from sqlalchemy import orm
from starlette.testclient import TestClient

from reports_service.api.app import create_app
from reports_service.db.models import Base
from reports_service.settings import ServiceConfig, get_config
from tests.helpers import (
    DBObjectCreator,
    FakeAuthServer,
    FakePaymentServer,
    clear_bucket,
)

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
def fake_auth_server() -> FakeAuthServer:
    return FakeAuthServer()


@pytest.fixture
def get_user_url(
    httpserver: HTTPServer,
    fake_auth_server: FakeAuthServer,
) -> str:
    path = "/user"
    url = f"http://127.0.0.1:{httpserver.port}{path}"
    (
        httpserver
        .expect_request(path, "GET")
        .respond_with_handler(
            func=fake_auth_server.handle_get_user_request,
        )
    )
    return url


@pytest.fixture
def fake_payment_server() -> FakePaymentServer:
    return FakePaymentServer()


@pytest.fixture
def create_payment_url(
    httpserver: HTTPServer,
    fake_payment_server: FakePaymentServer,
) -> str:
    path = "/payment"
    url = f"http://127.0.0.1:{httpserver.port}{path}"
    (
        httpserver
        .expect_request(path, "POST")
        .respond_with_handler(
            func=fake_payment_server.handle_create_payment_request,
        )
    )
    return url


@pytest.fixture
def set_env(
    get_user_url: str,
    create_payment_url: str,
) -> tp.Generator[None, None, None]:
    monkeypatch = MonkeyPatch()
    monkeypatch.setenv("GET_USER_URL", get_user_url)
    monkeypatch.setenv("CREATE_PAYMENT_URL", create_payment_url)
    monkeypatch.setenv("PAYMENT_SHOP_ID", "my_shop")
    monkeypatch.setenv("PAYMENT_SECRET_KEY", "super_secret")
    monkeypatch.setenv("PAYMENT_RETURN_URL", "my_site")
    monkeypatch.setenv("PRODUCT_CODE", "some_code")

    yield

    monkeypatch.undo()


@pytest.fixture
def service_config(set_env: None) -> ServiceConfig:
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
    clear_bucket(s3_client, bucket)
    s3_client.create_bucket(Bucket=bucket)

    yield

    clear_bucket(s3_client, bucket)


@pytest.fixture
def sqs_client(service_config: ServiceConfig) -> BaseClient:
    config = service_config.queue_config
    client = boto3.client(
        service_name="sqs",
        endpoint_url=config.endpoint_url,
        region_name=config.region,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )
    return client


@pytest.fixture
def sqs_queue_url(service_config: ServiceConfig) -> str:
    endpoint_url = service_config.queue_config.endpoint_url
    queue_name = service_config.queue_config.queue
    queue_url = urljoin(endpoint_url, f"queue/{queue_name}")
    return queue_url


@pytest.fixture
def sqs_queue(sqs_client: BaseClient, sqs_queue_url: str) -> tp.Iterator[None]:
    queue_name = sqs_queue_url.split("/")[-1]
    sqs_client.create_queue(QueueName=queue_name)

    yield

    sqs_client.delete_queue(QueueUrl=sqs_queue_url)


@pytest.fixture
def app(
    service_config: ServiceConfig,
    db_session: orm.Session,
    s3_bucket: None,
    sqs_queue: None,
) -> FastAPI:
    app = create_app(service_config)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app=app)


@pytest.fixture
def create_db_object(
    db_session: orm.Session,
) -> DBObjectCreator:
    assert db_session.is_active

    def create(obj: Base) -> None:
        db_session.add(obj)
        db_session.commit()

    return create
