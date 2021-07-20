from uuid import UUID

from fastapi import UploadFile
from pydantic.main import BaseModel


class StorageService(BaseModel):

    async def save_report(self, report_id: UUID, body: UploadFile) -> None:
        # TODO: implement
        pass
