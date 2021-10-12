from pydantic import BaseSettings, HttpUrl, PostgresDsn, validator


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
    get_user_url: HttpUrl
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


class ServiceConfig(Config):
    service_name: str = "reports_service"
    request_id_header: str = "X-Request-Id"

    log_config: LogConfig
    auth_service_config: AuthServiceConfig
    db_config: DBConfig
    storage_config: S3Config
    queue_config: SQSConfig


def get_config() -> ServiceConfig:
    return ServiceConfig(
        log_config=LogConfig(),
        auth_service_config=AuthServiceConfig(),
        db_config=DBConfig(db_pool_config=DBPoolConfig()),
        storage_config=S3Config(),
        queue_config=SQSConfig(),
    )
