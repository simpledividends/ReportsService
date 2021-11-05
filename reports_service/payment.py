import typing as tp
from decimal import Decimal
from http import HTTPStatus
from socket import AF_INET
from uuid import uuid4

import aiohttp
import jwt
from pydantic import BaseModel

from .context import REQUEST_ID
from .log import app_logger
from .models.payment import Price, Promocode, PromocodeUsage, YookassaEventBody
from .models.report import Report
from .models.user import User
from .utils import utc_now

RUBLE_CURRENCY = "RUB"
PENDING_STATUS = "pending"


class PaymentServiceError(Exception):
    pass


class PaymentService(BaseModel):
    create_payment_url: str
    shop_id: str
    secret_key: str
    return_url: str
    jwt_key: str
    vat_code: int
    payment_subject: str
    payment_mode: str
    product_code: str
    aiohttp_pool_size: int
    aiohttp_session_timeout: float
    jwt_algorithm: str
    session: tp.Optional[aiohttp.ClientSession] = None

    class Config:
        arbitrary_types_allowed = True

    def _make_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.aiohttp_session_timeout),
            connector=aiohttp.TCPConnector(
                family=AF_INET,
                limit_per_host=self.aiohttp_pool_size,
            )
        )

    def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = self._make_session()
        return self.session

    def setup(self) -> None:
        self._get_session()
        app_logger.info("Auth service initialized")

    async def cleanup(self) -> None:
        await self.session.close()
        self.session = None
        app_logger.info("Auth service shutdown")

    @classmethod
    def _make_payment_description(cls, report: Report) -> str:
        desc = f"Оплата отчета {report.broker} от {report.created_at}"
        return desc

    def _make_body(
        self,
        user: User,
        report: Report,
        promocode: tp.Optional[Promocode],
    ) -> tp.Dict[str, tp.Any]:
        if report.price is None:
            raise ValueError(f"Report {report.report_id} price is None")

        price = self.get_price_with_promocode(report, promocode)
        if (
            promocode is not None
            and price.promocode_usage == PromocodeUsage.success
        ):
            used_promocode = promocode.promocode
        else:
            used_promocode = None
        amount = {
            "value": str(price.final_price),
            "currency": RUBLE_CURRENCY,
        }
        receipt = {  # TODO: understand and finalize
            "customer": {
                "email": user.email,
            },
            "items": [
                {
                    "description": f"Отчет {report.report_id}",
                    "quantity": "1",
                    "amount": amount,
                    "vat_code": self.vat_code,
                    "payment_subject": self.payment_subject,
                    "payment_mode": self.payment_mode,
                    "product_code": self.product_code,
                },
            ],
        }
        token_body = {"id": str(uuid4())}
        metadata = {
            "user_id": str(user.user_id),
            "report_id": str(report.report_id),
            "request_id": REQUEST_ID.get(),
            "promocode": used_promocode,
            "token": jwt.encode(token_body, self.jwt_key, self.jwt_algorithm),
        }
        body = {
            "amount": amount,
            "description": self._make_payment_description(report),
            "receipt": receipt,
            "confirmation": {
                "type": "redirect",
                "locale": "ru_RU",
                "return_url": self.return_url,
            },
            "capture": True,
            "metadata": metadata,
        }
        return body

    async def create_payment(
        self,
        user: User,
        report: Report,
        promocode: tp.Optional[Promocode],
    ) -> tp.Tuple[str, tp.Dict[str, tp.Any]]:
        auth = aiohttp.BasicAuth(login=self.shop_id, password=self.secret_key)
        headers = {
            "Idempotence-Key": str(uuid4()),
            "Content-Type": "application/json",
        }
        body = self._make_body(user, report, promocode)

        async with self._get_session().post(
            url=self.create_payment_url,
            auth=auth,
            headers=headers,
            json=body,
        ) as resp:
            status_code = resp.status
            resp_body = await resp.json()

            if status_code != HTTPStatus.OK:
                raise PaymentServiceError(
                    f"Error while creating payment: bad API status code.  "
                    f"Status: {resp.status},  details: {resp_body}"
                )

            status = resp_body["status"]
            if status != PENDING_STATUS:
                raise PaymentServiceError(
                    "Not pending status returned after payment creation."
                    f"Returned status: '{status}'"
                )

            try:
                confirm_url = resp_body["confirmation"]["confirmation_url"]
            except (KeyError, TypeError) as e:
                raise PaymentServiceError(
                    f"No confirmation_url in API response body: {e!r}"
                )

            return confirm_url, body

    def verify_authenticity_of_webhook(
        self,
        event_body: YookassaEventBody,
    ) -> None:
        token = event_body.object["metadata"]["token"]
        jwt.decode(token, self.jwt_key, [self.jwt_algorithm])

    def get_price_with_promocode(
        self,
        report: Report,
        promocode: tp.Optional[Promocode],
    ) -> Price:
        discount = 0
        now = utc_now()
        if (
            promocode is None
            or promocode.rest_usages <= 0
            or (
                promocode.user_id is not None
                and promocode.user_id != report.user_id
            )
        ):
            promocode_usage = PromocodeUsage.not_exist
        elif promocode.valid_from > now or promocode.valid_to < now:
            promocode_usage = PromocodeUsage.expired
        else:
            discount = promocode.discount
            promocode_usage = PromocodeUsage.success

        final_price_float = float(report.price) * (1 - discount / 100)
        final_price = Decimal(str(round(final_price_float, 2)))

        price = Price(
            start_price=report.price,
            final_price=final_price,
            discount=discount,
            promocode_usage=promocode_usage,
        )
        return price
