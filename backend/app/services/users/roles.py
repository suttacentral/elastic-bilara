from app.core.config import settings
from app.db.models.user import Role
from app.db.schemas.user import UserBase
from app.services.users import utils
from search.search import Search
from search.utils import get_json_data

search = Search()


def add_role(data: dict[str, str]) -> UserBase:
    username: str = data.get("username")
    muids: list[str] = search.find_unique_data(field="muid")
    if any(utils.is_username_in_muid(username, muid) for muid in muids):
        return UserBase(**data, role=Role.WRITER.value)

    projects: list[dict] = get_json_data(settings.WORK_DIR / "_project-v2.json")
    if utils.check_creator_github_handle_in_list(username, projects):
        return UserBase(**data, role=Role.WRITER.value)

    publications: list[dict] = get_json_data(settings.WORK_DIR / "_publication-v2.json")
    if not utils.check_creator_github_handle_in_list(username, publications):
        return UserBase(**data, role=Role.REVIEWER.value)

    return UserBase(**data, role=Role.WRITER.value)


def get_role(github_id: int) -> str:
    return utils.get_user(github_id).role
