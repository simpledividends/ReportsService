import typing as tp
from http import HTTPStatus
from socket import AF_INET

import aiohttp
from pydantic import BaseModel

from reports_service.api.exceptions import ForbiddenException
from reports_service.context import REQUEST_ID
from reports_service.log import app_logger
from reports_service.models.user import User

AUTH_SERVISE_AUTHORIZATION_HEADER = "Authorization"


class AuthServiceError(Exception):
    pass


class AuthService(BaseModel):
    get_user_url: str
    request_id_header: str
    aiohttp_pool_size: int
    aiohttp_session_timeout: float
    session: tp.Optional[aiohttp.ClientSession] = None

    class Config:
        arbitrary_types_allowed = True

    def _make_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.aiohttp_session_timeout),
            connector=aiohttp.TCPConnector(
                family=AF_INET,
                limit_per_host=self.aiohttp_pool_size,
            )
        )

    def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = self._make_session()
        return self.session

    def setup(self) -> None:
        self._get_session()
        app_logger.info("Auth service initialized")

    async def cleanup(self) -> None:
        await self.session.close()
        self.session = None
        app_logger.info("Auth service shutdown")

    async def get_user(self, auth_header: tp.Optional[str]) -> User:
        headers = {self.request_id_header: REQUEST_ID.get()}
        if auth_header is not None:
            headers[AUTH_SERVISE_AUTHORIZATION_HEADER] = auth_header
        async with self._get_session().get(
            url=self.get_user_url,
            headers=headers,
        ) as resp:
            if resp.status == HTTPStatus.OK:
                resp_json = await resp.json()
                user = User(**resp_json)
                return user

            if resp.status == HTTPStatus.FORBIDDEN:
                resp_json = await resp.json()
                try:
                    error = resp_json["errors"][0]
                    raise ForbiddenException(
                        error_key=error["error_key"],
                        error_message=error["error_message"],
                    )
                except KeyError:
                    raise ForbiddenException()

            raise AuthServiceError(f"Auth server error: status {resp.status}")
