from uuid import UUID

from pydantic.main import BaseModel


class QueueService(BaseModel):

    async def send_parse_message(self, report_id: UUID) -> None:
        pass
