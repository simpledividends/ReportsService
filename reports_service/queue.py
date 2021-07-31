import base64
import typing as tp
import uuid
from urllib.parse import urljoin

import aioboto3
import orjson
from aiobotocore.session import ClientCreatorContext
from pydantic.main import BaseModel

from reports_service.context import REQUEST_ID

MessageBodyContent = tp.Tuple[tp.List[tp.Any], tp.Dict[str, tp.Any], None]


class QueueService(BaseModel):
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str
    queue: str
    parse_task: str

    def _client(self) -> ClientCreatorContext:
        session = aioboto3.Session()
        return session.client(
            service_name="sqs",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

    def _make_message(self, storage_key: str) -> str:
        msg_body_content: MessageBodyContent = (
            [],
            {"storage_key": storage_key, "request_id": REQUEST_ID.get("-")},
            None,
        )
        msg_body = base64.b64encode(orjson.dumps(msg_body_content)).decode()

        task_id = str(uuid.uuid4())
        msg_content = {
            "body": msg_body,
            "content-encoding": "utf-8",
            "content-type": "application/json",
            "headers": {
                "lang": "py",
                "task": self.parse_task,
                "id": task_id,
            },
            "properties": {
                "delivery_info": {},
                "body_encoding": 'base64',
            }
        }
        msg = base64.b64encode(orjson.dumps(msg_content)).decode()
        return msg

    @property
    def queue_url(self) -> str:
        return urljoin(self.endpoint_url, f"queue/{self.queue}")

    async def send_parse_message(self, storage_key: str) -> None:
        msg = self._make_message(storage_key)
        async with self._client() as client:
            await client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=msg,
            )
