from app.core.config import settings
from app.services.users.roles import Roles
from app.services.users.schema import UserData
from app.services.users.utils import get_user, is_username_in_muid
from search.utils import get_json_data


def can_edit_translation(github_id: int, muid: str) -> bool:
    user: UserData = get_user(github_id)
    if muid.startswith("translation") and is_username_in_muid(user.username, muid):
        return True
    projects: list[dict] = get_json_data(settings.WORK_DIR / "_project-v2.json")
    if user.role == Roles.PROOFREADER:
        return False
    if user.role == Roles.ADMIN:
        return True
    if user.role == Roles.TRANSLATOR:
        if any(owns_project(user.username, project, muid) for project in projects):
            return True
    return False


def owns_project(
    username: str,
    project: dict,
    muid: str,
) -> bool:
    return project.get("translation_muids") == muid and project.get("creator_github_handle") == username
