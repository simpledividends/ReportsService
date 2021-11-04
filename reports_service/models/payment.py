import typing as tp
from enum import Enum

from pydantic import BaseModel


class YookassaEvent(str, Enum):
    waiting_for_capture = "payment.waiting_for_capture"
    succeeded = "payment.succeeded"
    cancelled = "payment.canceled"
    refund_succeeded = "refund.succeeded"


class YookassaEventBody(BaseModel):
    type: str
    event: YookassaEvent
    object: tp.Dict[str, tp.Any]
