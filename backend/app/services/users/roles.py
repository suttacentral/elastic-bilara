from enum import Enum

from app.core.config import settings
from app.services.users import utils
from app.services.users.schema import UserData
from search.search import Search
from search.utils import get_json_data

search = Search()


class Role(Enum):
    PROOFREADER = "proofreader"
    TRANSLATOR = "translator"
    ADMIN = "admin"


def add_role(data: dict[str, str]) -> UserData:
    username: str = data.get("username")
    muids: list[str] = search.find_unique_data(field="muid")
    if any(utils.is_username_in_muid(username, muid) for muid in muids):
        return UserData(**data, role=Role.TRANSLATOR.value)

    projects: list[dict] = get_json_data(settings.WORK_DIR / "_project-v2.json")
    if utils.check_creator_github_handle_in_list(username, projects):
        return UserData(**data, role=Role.TRANSLATOR.value)

    publications: list[dict] = get_json_data(settings.WORK_DIR / "_publication-v2.json")
    if not utils.check_creator_github_handle_in_list(username, publications):
        return UserData(**data, role=Role.PROOFREADER.value)

    return UserData(**data, role=Role.TRANSLATOR.value)


def get_role(github_id: int) -> str:
    return utils.get_user(github_id).role
