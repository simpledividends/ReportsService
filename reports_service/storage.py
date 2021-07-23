from uuid import UUID

import aioboto3
from aiobotocore.session import ClientCreatorContext
from fastapi import UploadFile
from pydantic.main import BaseModel


class StorageService(BaseModel):
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str
    bucket: str
    report_body_key_template: str

    def _client(self) -> ClientCreatorContext:
        session = aioboto3.Session()
        return session.client(
            service_name="s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

    async def save_report(self, report_id: UUID, file: UploadFile) -> None:
        key = self.report_body_key_template.format(report_id=report_id)
        async with self._client() as client:
            await client.upload_fileobj(file, self.bucket, key)
