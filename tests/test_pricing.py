import typing as tp
from datetime import date, datetime
from decimal import Decimal

import pytest

from reports_service.models.report import ParsedReport
from reports_service.pricing import PriceService
from reports_service.settings import PriceStrategy

from .helpers import make_report_row

STRATEGIES = [
    PriceStrategy(
        started_at=datetime(2021, 10, 30),
        calculator="linear_with_min_threshold",
        params={"min_threshold": 10, "row_price": 1.001},
    ),
    PriceStrategy(
        started_at=datetime(2021, 11, 30),
        calculator="linear_with_min_threshold",
        params={"min_threshold": 100, "row_price": 1},
    ),
    PriceStrategy(
        started_at=datetime(2021, 12, 30),
        calculator="linear_with_min_threshold",
        params={"min_threshold": 200, "row_price": 1},
    ),
]
PARSED_REPORT = ParsedReport(
    broker="bbb",
    version="vvv",
    period=(date(2020, 5, 10), date(2020, 9, 11)),
    rows=[make_report_row(isin="isin1") for _ in range(19)]
)


@pytest.mark.parametrize(
    "created_at,expected_price",
    (
        (datetime(2021, 11, 20), Decimal('19.02')),
        (datetime(2021, 12, 20), Decimal('100')),
        (datetime(2021, 12, 30), Decimal('200')),
    )
)
def test_correct_choosing_price_strategy(
    created_at: datetime,
    expected_price: tp.Optional[Decimal],
) -> None:
    service = PriceService(strategies=STRATEGIES)
    price = service.calc(PARSED_REPORT, created_at)
    assert price == expected_price


def test_raises_when_created_before_min_date() -> None:
    service = PriceService(strategies=STRATEGIES)
    with pytest.raises(RuntimeError):
        service.calc(PARSED_REPORT, datetime(2021, 10, 20))
