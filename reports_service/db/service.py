import typing as tp
from uuid import UUID, uuid4

from asyncpg import Pool
from pydantic import BaseModel

from reports_service.log import app_logger
from reports_service.models.report import ParseStatus, Report
from reports_service.utils import utc_now


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
                , broker
                , year
        """
        record = await self.pool.fetchrow(
            query,
            uuid4(),
            user_id,
            filename,
            utc_now(),
            ParseStatus.in_progress,
        )
        return Report(**record)

    async def get_reports(self, user_id: UUID) -> tp.List[Report]:
        query = """
            SELECT *
            FROM reports
            WHERE user_id = $1::UUID
        """
        records = await self.pool.fetch(
            query,
            uuid4(),
        )
        return [Report(**record) for record in records]
