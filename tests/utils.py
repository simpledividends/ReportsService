import typing as tp
from datetime import datetime, timedelta
from uuid import UUID


class ApproxDatetime:

    def __init__(
        self,
        expected: datetime,
        abs_delta: timedelta = timedelta(seconds=10),
    ) -> None:
        self.min_ = expected - abs_delta
        self.max_ = expected + abs_delta

    def __eq__(self, actual: tp.Any) -> bool:
        if isinstance(actual, str):
            dt = datetime.fromisoformat(actual)
        elif isinstance(actual, datetime):
            dt = actual
        else:
            return False
        return self.min_ <= dt <= self.max_


class AnyUUID:

    def __init__(self, version: int = 4) -> None:
        self.version = version

    def __eq__(self, actual: tp.Any) -> bool:
        if not isinstance(actual, str):
            return False
        uuid = UUID(actual)
        return uuid.version == self.version


class AnyStr:

    def __eq__(self, o: object) -> bool:
        return isinstance(o, str)
