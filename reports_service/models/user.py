from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class User(BaseModel):
    user_id: UUID
    email: str
    name: str
    created_at: datetime
    verified_at: datetime
    role: UserRole
