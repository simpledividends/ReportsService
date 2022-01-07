import typing as tp
from datetime import date, datetime
from decimal import Decimal

import pytest

from reports_service.models.report import ParsedReport
from reports_service.pricing import PriceService
from reports_service.settings import PriceStrategy

from .helpers import make_report_row

LINEAR_STRATEGIES = [
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
THRESHOLD_STRATEGIES = [
    PriceStrategy(
        started_at=datetime(2021, 9, 30),
        calculator="thresholds",
        params={"n_rows_thresholds": [], "prices": [28]},
    ),
    PriceStrategy(
        started_at=datetime(2021, 10, 30),
        calculator="thresholds",
        params={"n_rows_thresholds": [10], "prices": [15, 30]},
    ),
    PriceStrategy(
        started_at=datetime(2021, 11, 30),
        calculator="thresholds",
        params={"n_rows_thresholds": [20], "prices": [15, 30]},
    ),
    PriceStrategy(
        started_at=datetime(2021, 12, 30),
        calculator="thresholds",
        params={"n_rows_thresholds": [10, 19], "prices": [15, 30, 45]},
    ),
]
PARSED_REPORT = ParsedReport(
    broker="bbb",
    version="vvv",
    period=(date(2020, 5, 10), date(2020, 9, 11)),
    rows=[make_report_row(isin="isin1") for _ in range(19)]
)


@pytest.mark.parametrize(
    "strategies,created_at,expected_price",
    (
        (LINEAR_STRATEGIES, datetime(2021, 11, 20), Decimal("19.02")),
        (LINEAR_STRATEGIES, datetime(2021, 12, 20), Decimal("100")),
        (LINEAR_STRATEGIES, datetime(2021, 12, 30), Decimal("200")),
        (THRESHOLD_STRATEGIES, datetime(2021, 10, 20), Decimal("28")),
        (THRESHOLD_STRATEGIES, datetime(2021, 11, 20), Decimal("30")),
        (THRESHOLD_STRATEGIES, datetime(2021, 12, 20), Decimal("15")),
        (THRESHOLD_STRATEGIES, datetime(2021, 12, 30), Decimal("30")),
    )
)
def test_correct_choosing_price_strategy(
    strategies: tp.List[PriceStrategy],
    created_at: datetime,
    expected_price: tp.Optional[Decimal],
) -> None:
    service = PriceService(strategies=strategies)
    price = service.calc(PARSED_REPORT, created_at)
    assert price == expected_price


@pytest.mark.parametrize(
    "strategies",
    (LINEAR_STRATEGIES, THRESHOLD_STRATEGIES),
)
def test_raises_when_created_before_min_date(
    strategies: tp.List[PriceStrategy],
) -> None:
    service = PriceService(strategies=strategies)
    with pytest.raises(RuntimeError):
        service.calc(PARSED_REPORT, datetime(2021, 9, 20))
