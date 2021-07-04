import logging.config
import typing as tp

from .context import REQUEST_ID
from .settings import ServiceConfig

app_logger = logging.getLogger("app")
access_logger = logging.getLogger("access")


ACCESS_LOG_FORMAT = (
    'remote_addr="%a" '
    'referer="%{Referer}i" '
    'user_agent="%{User-Agent}i" '
    'protocol="%r" '
    'response_code="%s" '
    'request_time="%Tf" '
)


class ServiceNameFilter(logging.Filter):

    def __init__(self, name: str = "", service_name: str = "") -> None:
        self.service_name = service_name

        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "service_name", self.service_name)

        return super().filter(record)


class RequestIDFilter(logging.Filter):
    def __init__(self, name: str = "") -> None:
        self.context_var = REQUEST_ID

        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = self.context_var.get("-")
        setattr(record, "request_id", request_id)
        return super().filter(record)


def get_config(service_config: ServiceConfig) -> tp.Dict[str, tp.Any]:
    level = service_config.log_config.level
    datetime_format = service_config.log_config.datetime_format

    config = {
        "version": 1,
        "disable_existing_loggers": True,
        "loggers": {
            "root": {
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            },
            app_logger.name: {
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            },
            access_logger.name: {
                "level": level,
                "handlers": ["access"],
                "propagate": False,
            },
            "gunicorn.error": {
                "level": "INFO",
                "handlers": [
                    "console",
                ],
                "propagate": False,
            },
            "gunicorn.access": {
                "level": "ERROR",
                "handlers": [
                    "gunicorn.access",
                ],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": [
                    "console",
                ],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "ERROR",
                "handlers": [
                    "gunicorn.access",
                ],
                "propagate": False,
            },
        },
        "handlers": {
            "console": {
                "formatter": "console",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["service_name", "request_id"],
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["service_name", "request_id"],
            },
            "gunicorn.access": {
                "class": "logging.StreamHandler",
                "formatter": "gunicorn.access",
                "stream": "ext://sys.stdout",
                "filters": ["service_name", "request_id"],
            },
        },
        "formatters": {
            "console": {
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'service_name="%(service_name)s" '
                    'logger="%(name)s" '
                    'pid="%(process)d" '
                    'request_id="%(request_id)s" '
                    'message="%(message)s" '
                ),
                "datefmt": datetime_format,
            },
            "access": {
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'service_name="%(service_name)s" '
                    'logger="%(name)s" '
                    'pid="%(process)d" '
                    'request_id="%(request_id)s" '
                    'method="%(method)s" '
                    'requested_url="%(requested_url)s" '
                    'status_code="%(status_code)s" '
                    'request_time="%(request_time)s" '
                ),
                "datefmt": datetime_format,
            },
            "gunicorn.access": {
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'logger="%(name)s" '
                    'pid="%(process)d" '
                    'request_id="%(request_id)s" '
                    '"%(message)s"'
                ),
                "datefmt": datetime_format,
            },
        },
        "filters": {
            "service_name": {
                "()": "reports_service.log.ServiceNameFilter",
                "service_name": service_config.service_name,
            },
            "request_id": {"()": "reports_service.log.RequestIDFilter"},
        },
    }

    return config


def setup_logging(service_config: ServiceConfig) -> None:
    config = get_config(service_config)
    logging.config.dictConfig(config)
