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


calculators = {
    "linear_with_min_threshold": linear_with_min_threshold_calculator,
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
        float_price = calculator(parsed_report, **calculator_params)
        price = Decimal(str(round(float_price, 2)))
        return price
