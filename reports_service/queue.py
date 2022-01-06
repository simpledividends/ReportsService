import base64
import typing as tp
import uuid
from urllib.parse import urljoin

import aioboto3
import orjson
from aiobotocore.session import ClientCreatorContext
from pydantic.main import BaseModel

from reports_service.context import REQUEST_ID
from reports_service.utils import utc_now

MessageBodyContent = tp.Tuple[tp.List[tp.Any], tp.Dict[str, tp.Any], None]


class QueueService(BaseModel):
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str
    queue_path: str
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

    def _make_message(self, report_id: str, storage_key: str) -> str:
        kwargs = {
            "report_id": report_id,
            "storage_key": storage_key,
            "request_id": REQUEST_ID.get("-"),
        }
        message_id = str(uuid.uuid4())
        ts = int(utc_now().timestamp() * 1000)
        msg_content = {
            "queue_name": self.queue_name,
            "actor_name": self.parse_task,
            "args": [],
            "kwargs": kwargs,
            "options": {},
            "message_id": message_id,
            "message_timestamp": ts,
        }
        msg = base64.b64encode(orjson.dumps(msg_content)).decode()
        return msg

    @property
    def queue_url(self) -> str:
        return urljoin(self.endpoint_url, self.queue_path)

    @property
    def queue_name(self) -> str:
        return self.queue_path.split("/")[-1]

    async def send_parse_message(self, report_id: uuid.UUID, key: str) -> None:
        msg = self._make_message(str(report_id), key)
        async with self._client() as client:
            await client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=msg,
            )
