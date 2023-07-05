import json

from app.core.config import settings
from app.services.users.roles import add_role
from app.services.users.schema import UserData
from app.services.users.utils import get_user
from search.utils import get_json_data


def add_user_to_users_json(data: dict[str, str | int]) -> (bool, UserData | None):
    if settings.USERS_FILE.stat().st_size == 0:
        users = []
    else:
        users = get_json_data(settings.USERS_FILE)

    if not data.get("github_id"):
        return False, None

    if data["github_id"] in [user["github_id"] for user in users]:
        return False, get_user(data["github_id"])

    users.append(add_role(data).dict())
    with open(settings.USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

    return True, get_user(data["github_id"])
