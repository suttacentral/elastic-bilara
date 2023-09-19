import random
from typing import Any

from app.db.models.user import Role
from app.db.schemas.user import UserBase


class UserFactory:
    @staticmethod
    def create_user(**kwargs) -> UserBase:
        default_data: dict[str, Any] = {
            "github_id": random.randint(1, 1000),
            "username": "user" + str(random.randint(1, 1000)),
            "email": "user" + str(random.randint(1, 1000)) + "@test.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/" + str(random.randint(1, 1000)) + "?v=4",
            "role": random.choice(list(Role)).value,
        }
        data: dict[str, Any] = {**default_data, **kwargs}
        return UserBase(**data)

    @staticmethod
    def create_users(n, **kwargs) -> list[UserBase]:
        return [
            UserFactory.create_user(**{k: v[i] if isinstance(v, list) and i < len(v) else v for k, v in kwargs.items()})
            for i in range(n)
        ]
