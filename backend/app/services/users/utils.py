from app.core.config import settings
from app.services.users.schema import UserData
from search.utils import get_json_data


def get_user(github_id: int) -> UserData:
    users = get_json_data(settings.USERS_FILE)
    return UserData(**[user for user in users if user["github_id"] == github_id][0])


def is_username_in_muid(username: str, muid: str) -> bool:
    return username == muid.split("-", 2)[2]
