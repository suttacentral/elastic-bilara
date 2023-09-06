from app.core.config import settings
from app.db.models.user import Role
from app.db.schemas.user import UserBase
from app.services.users.utils import get_user, is_username_in_muid
from search.utils import get_json_data


def can_edit_translation(github_id: int, muid: str) -> bool:
    user: UserBase = get_user(github_id)
    if user.role == Role.ADMIN.value:
        return True
    if user.role == Role.REVIEWER.value:
        return False
    if muid.startswith("translation") and is_username_in_muid(user.username, muid):
        return True
    projects: list[dict] = get_json_data(settings.WORK_DIR / "_project-v2.json")
    if user.role == Role.WRITER.value:
        if any(owns_project(user.username, project, muid) for project in projects):
            return True
    return False


def owns_project(
    username: str,
    project: dict,
    muid: str,
) -> bool:
    return project.get("translation_muids") == muid and project.get("creator_github_handle") == username
