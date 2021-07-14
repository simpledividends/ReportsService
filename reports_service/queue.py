from datetime import datetime
from uuid import uuid4, UUID
import typing as tp

from pydantic.main import BaseModel

from reports_service.models.user import User, UserRole


class QueueService(BaseModel):

    async def send_parse_message(self, report_id: UUID) -> None:
        pass

