import typing as tp
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from reports_service.models.report import ParsedReport

from .settings import PriceStrategy


def linear_with_min_threshold_calculator(
    parsed_report: ParsedReport,
    min_threshold: float,
    row_price: float,
) -> float:
    # What if there are 0 rows?
    n_rows = len(parsed_report.rows)
    price = max(min_threshold, row_price * n_rows)
    return price


def thresholds_calculator(
    parsed_report: ParsedReport,
    n_rows_thresholds: tp.List[int],
    prices: tp.List[float],
) -> float:
    if len(n_rows_thresholds) != len(prices) - 1:
        raise ValueError("Must be: len(n_rows_thresholds) == len(prices) - 1")
    if sorted(n_rows_thresholds) != n_rows_thresholds:
        raise ValueError("n_rows_thresholds must be sorted")
    n_rows = len(parsed_report.rows)
    for i, n_rows_thr in enumerate(n_rows_thresholds):
        if n_rows <= n_rows_thr:
            price = prices[i]
            break
    else:
        price = prices[-1]
    return price


calculators = {
    "linear_with_min_threshold": linear_with_min_threshold_calculator,
    "thresholds": thresholds_calculator,
}


class PriceService(BaseModel):
    strategies: tp.List[PriceStrategy]

    def calc(
        self,
        parsed_report: ParsedReport,
        created_at: datetime,
    ) -> Decimal:
        for strategy in self.strategies[::-1]:
            if strategy.started_at <= created_at:
                calculator_name = strategy.calculator
                calculator_params = strategy.params
                break
        else:
            raise RuntimeError("No appropriate price strategy")

        calculator = calculators[calculator_name]
        float_price = calculator(  # type: ignore
            parsed_report,
            **calculator_params,
        )
        price = Decimal(str(round(float_price, 2)))
        return price
