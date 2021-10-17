import typing as tp
from uuid import UUID, uuid4

from asyncpg import Pool, Record
from pydantic import BaseModel

from reports_service.log import app_logger
from reports_service.models.report import (
    ExtendedParsedReportInfo,
    ParseStatus,
    ParsedReportRow,
    Report,
    SimpleReportRow,
)
from reports_service.utils import utc_now


def convert_period(record: Record) -> tp.Dict[str, tp.Any]:
    record_dict = dict(**record)
    record_dict["period"] = (
        record_dict.pop("period_start"),
        record_dict.pop("period_end"),
    )
    if record_dict["period"] == (None, None):
        record_dict["period"] = None
    return record_dict


class DBService(BaseModel):
    pool: Pool

    class Config:
        arbitrary_types_allowed = True

    async def setup(self) -> None:
        await self.pool
        app_logger.info("Db service initialized")

    async def cleanup(self) -> None:
        await self.pool.close()
        app_logger.info("Db service shutdown")

    async def ping(self) -> bool:
        return await self.pool.fetchval("SELECT TRUE")

    async def add_new_report(self, user_id: UUID, filename: str) -> Report:
        query = """
            INSERT INTO reports
                (report_id, user_id, filename, created_at, parse_status)
            VALUES
                (
                    $1::UUID
                    , $2::UUID
                    , $3::VARCHAR
                    , $4::TIMESTAMP
                    , $5::parse_status_enum
                )
            RETURNING
                report_id
                , user_id
                , filename
                , created_at
                , parse_status
                , parsed_at
                , broker
                , period_start
                , period_end
                , year
                , parse_note
                , parser_version
        """
        record = await self.pool.fetchrow(
            query,
            uuid4(),
            user_id,
            filename,
            utc_now(),
            ParseStatus.in_progress,
        )
        return Report(**convert_period(record))

    async def get_report(self, report_id: UUID) -> Report:
        query = """
            SELECT *
            FROM reports
            WHERE report_id = $1::UUID
        """
        record = await self.pool.fetchrow(query, report_id)
        res = Report(**convert_period(record)) if record is not None else None
        return res

    async def get_reports(self, user_id: UUID) -> tp.List[Report]:
        query = """
            SELECT *
            FROM reports
            WHERE user_id = $1::UUID
        """
        records = await self.pool.fetch(query, user_id)
        return [Report(**convert_period(record)) for record in records]

    async def delete_report_rows(self, report_id: UUID) -> None:
        query = """
            DELETE FROM report_rows
            WHERE report_id = $1::UUID
        """
        await self.pool.execute(query, report_id)

    async def add_report_rows(
        self,
        report_id: UUID,
        rows: tp.List[ParsedReportRow],
    ) -> None:
        query = """
            INSERT INTO report_rows
                (
                    report_id
                    , row_n
                    , isin
                    , name
                    , tax_rate
                    , country_code
                    , income_amount
                    , income_date
                    , income_currency_rate
                    , tax_payment_date
                    , payed_tax_amount
                    , tax_payment_currency_rate
                )
            VALUES
                (
                    $1::UUID
                    , $2::INTEGER
                    , $3::VARCHAR
                    , $4::VARCHAR
                    , $5::VARCHAR
                    , $6::VARCHAR
                    , $7::FLOAT
                    , $8::DATE
                    , $9::FLOAT
                    , $10::DATE
                    , $11::FLOAT
                    , $12::FLOAT
                )
        """
        values = (
            (
                report_id,
                row_n,
                row.isin,
                row.name,
                row.tax_rate,
                row.country_code,
                row.income_amount,
                row.income_date,
                row.income_currency_rate,
                row.tax_payment_date,
                row.payed_tax_amount,
                row.tax_payment_currency_rate,
            )
            for row_n, row in enumerate(rows, 1)
        )
        await self.pool.executemany(query, values)

    async def update_parsed_report(
        self,
        report_id: UUID,
        parse_status: ParseStatus,
        report_info: tp.Optional[ExtendedParsedReportInfo],
    ) -> None:
        query = """
            UPDATE reports
            SET
                parse_status = $2::parse_status_enum
                , parsed_at = $3::TIMESTAMP
                , broker = $4::VARCHAR
                , period_start = $5::DATE
                , period_end = $6::DATE
                , year = $7::SMALLINT
                , parse_note = $8::VARCHAR
                , parser_version = $9::VARCHAR
            WHERE report_id = $1::UUID
        """
        if report_info is not None:
            info_values = (
                report_info.broker,
                report_info.period[0],
                report_info.period[1],
                report_info.year,
                report_info.note,
                report_info.version,
            )
        else:
            info_values = (None, None, None, None, None, None)
        await self.pool.execute(
            query,
            report_id,
            parse_status,
            utc_now(),
            *info_values,
        )

    async def get_report_rows(
        self,
        report_id: UUID,
    ) -> tp.List[SimpleReportRow]:
        query = """
            SELECT row_n, name, income_amount, income_date, payed_tax_amount
            FROM report_rows
            WHERE report_id = $1::UUID
            ORDER BY row_n
        """
        records = await self.pool.fetch(query, report_id)
        return [SimpleReportRow(**record) for record in records]
