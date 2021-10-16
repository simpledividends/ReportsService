import typing as tp

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from reports_service.log import app_logger
from reports_service.models.user import User, UserRole
from reports_service.services import get_auth_service

from .exceptions import ForbiddenException

AUTHORIZATION_HEADER = "Authorization"


auth_api_key_header = APIKeyHeader(
    name=AUTHORIZATION_HEADER,
    auto_error=False,
)


async def get_request_user(
    request: Request,
    header: tp.Optional[str] = Security(auth_api_key_header),
) -> User:
    auth_service = get_auth_service(request.app)
    user = await auth_service.get_user(header)

    app_logger.info(f"Request from user {user.user_id}")
    return user


async def get_service_user(
    request: Request,
    header: tp.Optional[str] = Security(auth_api_key_header),
) -> User:
    user = await get_request_user(request, header)
    if user.role != UserRole.service:
        raise ForbiddenException()
    app_logger.info(f"Request from service user {user.user_id} {user.name}")
    return user
