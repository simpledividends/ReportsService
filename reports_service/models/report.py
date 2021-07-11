from enum import Enum


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
