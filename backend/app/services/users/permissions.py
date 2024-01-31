from app.core.config import settings
from app.db.models.user import Role
from app.db.schemas.user import User, UserBase
from app.services.auth.utils import get_credentials_exception
from app.services.users.utils import get_user, is_username_in_muid
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
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


def is_user_in_admin_group(user: UserBase) -> bool:
    return user.role in [Role.ADMIN.value, Role.SUPERUSER.value]


def get_github_id_from_cookie(request: Request) -> int:
    token = request.cookies.get("access_token")
    if not token:
        raise get_credentials_exception()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
        github_id: str = payload.get("sub")
        if not github_id:
            raise get_credentials_exception()
        return int(github_id)
    except JWTError:
        raise get_credentials_exception()


def get_user_from_cookie(request: Request) -> User:
    github_id: int = get_github_id_from_cookie(request)
    user: User = get_user(github_id)
    if not user:
        raise get_credentials_exception()
    return user


def is_admin_or_superuser(request: Request) -> bool:
    user: User = get_user_from_cookie(request)
    if not is_user_in_admin_group(user):
        raise get_credentials_exception()
    return True


def is_user_active(request: Request) -> bool:
    user: User = get_user_from_cookie(request)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"User is not active")
    return True


def can_create_projects(github_id: int) -> bool:
    user: UserBase = get_user(github_id)
    if user.role == Role.ADMIN.value or user.role == Role.SUPERUSER.value:
        return True
    return False
