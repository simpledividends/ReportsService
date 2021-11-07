import typing as tp
from datetime import datetime

from pydantic import BaseSettings, PostgresDsn, validator
from pydantic.main import BaseModel


class Config(BaseSettings):

    class Config:
        case_sensitive = False


class LogConfig(Config):
    level: str = "INFO"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"

    class Config:
        case_sensitive = False
        fields = {
            "level": {
                "env": ["log_level"]
            },
        }


class AuthServiceConfig(Config):
    get_user_url: str
    auth_service_request_id_header: str = "X-Request-Id"
    aiohttp_pool_size: int = 100
    aiohttp_session_timeout: float = 5


class DBPoolConfig(Config):
    db_url: PostgresDsn
    min_size: int = 0
    max_size: int = 20
    max_queries: int = 1000
    max_inactive_connection_lifetime: int = 3600
    timeout: float = 10
    command_timeout: float = 10
    statement_cache_size: int = 1024
    max_cached_statement_lifetime: int = 3600


class DBConfig(Config):
    db_pool_config: DBPoolConfig


class S3Config(Config):
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str
    bucket: str
    report_body_key_template: str = "report_bodies/{report_id}"

    class Config:
        case_sensitive = False
        env_prefix = "S3_"

    @validator('report_body_key_template')
    def present_report_id_substitution(  # pylint: disable=no-self-argument
        cls,
        key: str,
    ) -> str:
        if "{report_id}" not in key:
            raise ValueError("Must contain substitution for report_id")
        return key


class SQSConfig(Config):
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str
    queue: str
    parse_task: str

    class Config:
        case_sensitive = False
        env_prefix = "SQS_"


class PriceStrategy(BaseModel):
    started_at: datetime
    calculator: str
    params: tp.Dict[str, tp.Any]


class PriceConfig(Config):
    # TODO: think about it
    strategies: tp.List[PriceStrategy] = [  # ordered by date
        PriceStrategy(
            started_at=datetime(2021, 6, 30),
            calculator="linear_with_min_threshold",
            params={"min_threshold": 100, "row_price": 1},
        ),
    ]


class PaymentConfig(Config):
    create_payment_url: str
    shop_id: str
    secret_key: str
    return_url: str
    jwt_key: str
    product_code: str  # TODO: think
    vat_code: int = 4  # TODO: think
    payment_subject: str = "service"  # TODO: think
    payment_mode: str = "full_payment"  # TODO: think
    aiohttp_pool_size: int = 10
    aiohttp_session_timeout: float = 10
    jwt_algorithm: str = "HS256"

    class Config:
        case_sensitive = False
        fields = {
            "shop_id": {"env": ["payment_shop_id"]},
            "secret_key": {"env": ["payment_secret_key"]},
            "return_url": {"env": ["payment_return_url"]},
            "jwt_key": {"env": ["payment_jwt_key"]},
            "aiohttp_pool_size": {"env": ["payment_aiohttp_pool_size"]},
            "aiohttp_session_timeout": {
                "env": ["payment_aiohttp_session_timeout"],
            },
            "jwt_algorithm": {"env": ["payment_jwt_algorithm"]},
        }


class ServiceConfig(Config):
    max_report_size: int = 5_000_000  # bytes
    max_user_reports: int = 100
    max_report_filename_length: int = 128
    service_name: str = "reports_service"
    request_id_header: str = "X-Request-Id"

    log_config: LogConfig
    auth_service_config: AuthServiceConfig
    db_config: DBConfig
    storage_config: S3Config
    queue_config: SQSConfig
    price_config: PriceConfig
    payment_config: PaymentConfig


def get_config() -> ServiceConfig:
    return ServiceConfig(
        log_config=LogConfig(),
        auth_service_config=AuthServiceConfig(),
        db_config=DBConfig(db_pool_config=DBPoolConfig()),
        storage_config=S3Config(),
        queue_config=SQSConfig(),
        price_config=PriceConfig(),
        payment_config=PaymentConfig(),
    )
