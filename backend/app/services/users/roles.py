from enum import Enum

from app.core.config import settings
from app.services.users.schema import UserData
from app.services.users.utils import get_user, is_username_in_muid
from search.search import Search
from search.utils import get_json_data

search = Search()


class Roles(Enum):
    PROOFREADER = "proofreader"
    TRANSLATOR = "translator"
    ADMIN = "admin"


def check_creator_github_handle_in_list(username: str, item_list: list[dict]):
    return username in [item["creator_github_handle"] for item in item_list]


def add_role(data: dict[str, str]) -> UserData:
    username = data["username"]
    muids = search.find_unique_data(field="muid")
    if any(is_username_in_muid(username, muid) for muid in muids):
        return UserData(**data, role=Roles.TRANSLATOR.value)

    projects = get_json_data(settings.WORK_DIR / "_project-v2.json")
    if check_creator_github_handle_in_list(username, projects):
        return UserData(**data, role=Roles.TRANSLATOR.value)

    publications = get_json_data(settings.WORK_DIR / "_publication-v2.json")
    if check_creator_github_handle_in_list(username, publications):
        return UserData(**data, role=Roles.TRANSLATOR.value)

    return UserData(**data, role=Roles.PROOFREADER.value)


def get_role(github_id: int) -> str:
    return get_user(github_id).role
