import typing as tp
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic.main import BaseModel


class Broker(str, Enum):
    tinkoff = "tinkoff"
    alfa = "alfa"
    bcs = "bcs"
    open = "open"
    finam = "finam"
    vtb = "vtb"
    sber = "sber"


class ParseStatus(str, Enum):
    in_progress = "in_progress"
    parsed = "parsed"
    not_parsed = "not_parsed"


class Report(BaseModel):
    report_id: UUID
    user_id: UUID
    filename: str
    created_at: datetime
    parse_status: ParseStatus
    broker: tp.Optional[Broker]
    year: tp.Optional[int]
