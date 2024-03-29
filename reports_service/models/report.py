import typing as tp
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import validator
from pydantic.main import BaseModel

Period = tp.Tuple[date, date]


class ParseStatus(str, Enum):
    in_progress = "in_progress"
    parsed = "parsed"
    not_parsed = "not_parsed"


class PaymentStatus(str, Enum):
    not_payed = "not_payed"
    in_progress = "in_progress"
    payed = "payed"
    error = "error"


class BaseReportInfo(BaseModel):
    report_id: UUID
    user_id: UUID
    filename: str
    created_at: datetime
    payment_status: PaymentStatus
    parse_status: ParseStatus
    price: tp.Optional[Decimal]
    is_ready_to_use: bool = False

    @validator("is_ready_to_use", always=True)
    def define_is_parsed(  # pylint: disable=no-self-argument
        cls,
        value: tp.Optional[bool],
        values: tp.Dict[str, tp.Any],
        **kwargs,
    ):
        is_ready = (
            values["parse_status"] == ParseStatus.parsed
            and (
                values["payment_status"] == PaymentStatus.payed
                or values["price"] == 0
            )
        )
        return is_ready


class ParsedReportRow(BaseModel):
    isin: str
    name: str
    tax_rate: str
    country_code: str
    currency_code: str
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
    year: tp.Optional[int]
    price: Decimal


class ParsedReport(ParsedReportInfo):
    rows: tp.List[ParsedReportRow]


class ParsingResult(BaseModel):
    parsed_report: tp.Optional[ParsedReport]
    message: tp.Optional[str]
    is_parsed: bool


class Report(BaseReportInfo):
    parsed_at: tp.Optional[datetime]
    broker: tp.Optional[str]
    period: tp.Optional[Period]
    year: tp.Optional[int]
    parse_note: tp.Optional[str]
    parser_version: tp.Optional[str]


class ReportPart(BaseModel):
    year: int
    n_rows: int


class DetailedReport(Report):
    parts: tp.List[ReportPart]


class DetailedReports(BaseModel):
    reports: tp.List[DetailedReport]


class SimpleReportRow(BaseModel):
    row_n: int
    name: str
    income_amount: float
    income_date: date
    payed_tax_amount: tp.Optional[float]
    currency_code: str


class SimpleReportRows(BaseModel):
    rows: tp.List[SimpleReportRow]


class DetailedReportRow(BaseModel):
    name_full: str
    tax_rate: str
    country_code: str
    source_country_code: str
    target_country_code: str
    currency_code: str
    income_amount: float
    income_date: date
    income_currency_rate: float
    tax_payment_date: tp.Optional[date]
    payed_tax_amount: tp.Optional[float]
    tax_payment_currency_rate: tp.Optional[float]


class DetailedReportRows(BaseModel):
    rows: tp.List[DetailedReportRow]
