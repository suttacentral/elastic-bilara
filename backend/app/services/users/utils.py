import json

from app.core.config import settings
from app.services.users.roles import add_role
from app.services.users.schema import UserData
from search.utils import get_json_data


def get_user(github_id: int) -> UserData:
    users: list[dict[str, str]] = get_json_data(settings.USERS_FILE)
    return UserData(**[user for user in users if user["github_id"] == github_id][0])


def is_username_in_muid(username: str, muid: str) -> bool:
    if not username or not muid:
        return False
    return username == muid.split("-", 2)[2]


def check_creator_github_handle_in_list(username: str, item_list: list[dict]) -> bool:
    return username in [item["creator_github_handle"] for item in item_list]


def add_user_to_users_json(data: dict[str, str | int]) -> tuple[bool, UserData | None]:
    try:
        if settings.USERS_FILE.stat().st_size == 0:
            users: list[dict[str, str]] = []
        else:
            users: list[dict[str, str]] = get_json_data(settings.USERS_FILE)
    except FileNotFoundError:
        users: list[dict[str, str]] = []

    if not data.get("github_id"):
        return False, None

    if data["github_id"] in [user["github_id"] for user in users]:
        return False, get_user(data["github_id"])

    users.append(add_role(data).dict())
    with open(settings.USERS_FILE, "w") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

    return True, get_user(data["github_id"])
