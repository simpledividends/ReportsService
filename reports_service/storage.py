from datetime import datetime
from uuid import uuid4, UUID
import typing as tp

from fastapi import UploadFile
from pydantic.main import BaseModel


class StorageService(BaseModel):

    async def save_report(self, report_id: UUID, body: UploadFile) -> None:
        # TODO: implement
        pass

