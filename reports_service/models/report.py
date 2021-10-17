import typing as tp
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic.main import BaseModel

Period = tp.Tuple[date, date]


class ParseStatus(str, Enum):
    in_progress = "in_progress"
    parsed = "parsed"
    not_parsed = "not_parsed"


class BaseReportInfo(BaseModel):
    report_id: UUID
    user_id: UUID
    filename: str
    created_at: datetime
    parse_status: ParseStatus


class ParsedReportRow(BaseModel):
    isin: str
    name_full: str
    name: str
    tax_rate: str
    country_code: str
    income_amount: float
    income_date: date
    income_currency_rate: float
    tax_payment_date: tp.Optional[date]
    payed_tax_amount: tp.Optional[float]
    tax_payment_currency_rate: tp.Optional[float]


class ParsedReportInfo(BaseModel):
    broker: str
    version: str
    period: Period
    note: tp.Optional[str]


class ExtendedParsedReportInfo(ParsedReportInfo):
    year: int


class ParsedReport(ParsedReportInfo):
    rows: tp.List[ParsedReportRow]


class ParsingResult(BaseModel):
    parsed_report: tp.Optional[ParsedReport]
    message: tp.Optional[str]
    is_parsed: tp.Optional[bool]


class Report(BaseReportInfo, ExtendedParsedReportInfo):
    pass


class Reports(BaseModel):
    reports: tp.List[Report]
