from asyncpg import Pool
from pydantic import BaseModel

from reports_service.log import app_logger


class DBService(BaseModel):
    pool: Pool
    max_active_newcomers_with_same_email: int
    max_active_requests_change_same_email: int
    max_active_user_password_tokens: int
    n_transaction_retries: int
    transaction_retry_interval_first: float
    transaction_retry_interval_factor: float

    class Config:
        arbitrary_types_allowed = True

    async def setup(self) -> None:
        await self.pool
        app_logger.info("Auth service initialized")

    async def cleanup(self) -> None:
        await self.pool.close()
        app_logger.info("Auth service shutdown")

    async def ping(self) -> bool:
        return await self.pool.fetchval("SELECT TRUE")
