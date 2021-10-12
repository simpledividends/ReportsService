import typing as tp
from http import HTTPStatus


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        error_key: str,
        error_message: str = "",
        error_loc: tp.Optional[tp.Sequence[str]] = None,
    ) -> None:
        self.error_key = error_key
        self.error_message = error_message
        self.error_loc = error_loc
        self.status_code = status_code
        super().__init__()


class ForbiddenException(AppException):
    def __init__(
        self,
        status_code: int = HTTPStatus.FORBIDDEN,
        error_key: str = "forbidden",
        error_message: str = "Forbidden",
        error_loc: tp.Optional[tp.Sequence[str]] = None,
    ):
        super().__init__(status_code, error_key, error_message, error_loc)
