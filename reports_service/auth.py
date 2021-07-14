from datetime import datetime
from uuid import uuid4
import typing as tp

from pydantic.main import BaseModel

from reports_service.models.user import User, UserRole


class AuthService(BaseModel):

    async def get_user(self, _: tp.Optional[str]) -> User:
        # TODO: remove mock, add request to auth service
        return User(
            user_id=uuid4(),
            email="user@ma.il",
            name="user name",
            created_at=datetime(2021, 6, 15),
            verified_at=datetime(2021, 6, 15),
            role=UserRole.user,
        )

