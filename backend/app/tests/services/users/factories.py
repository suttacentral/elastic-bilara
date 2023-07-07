import random

from app.services.users.roles import Role
from app.services.users.schema import UserData


class UserFactory:
    @staticmethod
    def create_user(**kwargs):
        default_data = {
            "github_id": random.randint(1, 1000),
            "username": "user" + str(random.randint(1, 1000)),
            "email": "user" + str(random.randint(1, 1000)) + "@test.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/" + str(random.randint(1, 1000)) + "?v=4",
            "role": random.choice(list(Role)).value,
        }
        data = {**default_data, **kwargs}
        return UserData(**data)

    @staticmethod
    def create_users(n, **kwargs):
        return [
            UserFactory.create_user(**{k: v[i] if isinstance(v, list) and i < len(v) else v for k, v in kwargs.items()})
            for i in range(n)
        ]
