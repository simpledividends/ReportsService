import typing as tp
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class YookassaEvent(str, Enum):
    waiting_for_capture = "payment.waiting_for_capture"
    succeeded = "payment.succeeded"
    cancelled = "payment.canceled"
    refund_succeeded = "refund.succeeded"


class YookassaEventBody(BaseModel):
    type: str
    event: YookassaEvent
    object: tp.Dict[str, tp.Any]


class Promocode(BaseModel):
    promocode: str
    user_id: tp.Optional[UUID]
    valid_from: datetime
    valid_to: datetime
    rest_usages: int
    discount: int = Field(ge=0, le=100)  # in percents


class PromocodeUsage(str, Enum):
    not_set = "not_set"
    success = "success"
    not_exist = "not_exist"
    expired = "expired"


class Price(BaseModel):
    start_price: Decimal
    final_price: Decimal
    discount: int  # in percents
    promocode_usage: PromocodeUsage
