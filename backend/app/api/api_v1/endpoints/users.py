from typing import Annotated, Any, Optional

from app.db.database import get_sess
from app.db.models.user import Role
from app.db.models.user import User as mUser
from app.db.schemas.user import User, UserBase, UserResponse, UserUpdatePayload, UserWithoutEmail
from app.services.auth import utils as auth_utils
from app.services.users import permissions, utils
from app.services.users.utils import is_user_active
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic_core import ValidationError

router = APIRouter(prefix="/users")


def serialize_user_for_requester(user: User, requester: User) -> UserResponse:
    validated_user = User.model_validate(user)
    if requester.role == Role.SUPERUSER.value:
        return UserWithoutEmail.model_validate(validated_user)
    return validated_user


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[UserResponse], description="Get all users")
async def get_users(requester: Annotated[User, Depends(permissions.is_admin_or_superuser)]) -> list[UserResponse]:
    with get_sess() as sess:
        users = sess.query(mUser).all()
        return [serialize_user_for_requester(user, requester) for user in users]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse, description="Create a new user")
async def create_user(
    user: UserBase, requester: Annotated[User, Depends(permissions.is_admin_or_superuser)]
) -> UserResponse:
    try:
        UserBase.model_validate(user)
        with get_sess() as sess:
            if sess.query(mUser).filter(mUser.github_id == user.github_id).first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f'"{user.github_id}" github_id already exists'
                )
            if sess.query(mUser).filter(mUser.username == user.username).first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f'User "{user.username}" already exists'
                )
            if sess.query(mUser).filter(mUser.email == user.email).first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f'User email "{user.email}" already in use'
                )
            sess.add(mUser(**user.model_dump()))
            sess.commit()
            created_user = User.model_validate(sess.query(mUser).filter(mUser.github_id == user.github_id).first())
            return serialize_user_for_requester(created_user, requester)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)


@router.delete("/{github_id}/", status_code=status.HTTP_200_OK, description="Delete a user")
async def delete_user(github_id: int) -> None:
    try:
        with get_sess() as sess:
            user = sess.query(mUser).filter(mUser.github_id == github_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")
            sess.delete(user)
            sess.commit()
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.get("/{github_id}/", response_model=UserResponse, description="Get a user")
async def get_user(
    github_id: int, requester: Annotated[User, Depends(permissions.is_admin_or_superuser)]
) -> UserResponse:
    try:
        return serialize_user_for_requester(utils.get_user(github_id), requester)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.get("/{github_id}/is_active", response_model=bool, description="Check if a user is active")
async def get_user_is_active(github_id: int) -> bool:
    try:
        return is_user_active(utils.get_user(github_id))
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/activate", response_model=UserResponse, description="Activate a user")
async def activate_user(
    github_id: int, requester: Annotated[User, Depends(permissions.is_admin_or_superuser)]
) -> UserResponse:
    try:
        with get_sess() as sess:
            user = sess.query(mUser).filter(mUser.github_id == github_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")
            if is_user_active(user):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {github_id} is already active"
                )
            user.is_active = True
            sess.add(user)
            sess.commit()
            return serialize_user_for_requester(User.model_validate(user), requester)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/deactivate", response_model=UserResponse, description="Deactivate a user")
async def deactivate_user(
    github_id: int, requester: Annotated[User, Depends(permissions.is_admin_or_superuser)]
) -> UserResponse:
    try:
        with get_sess() as sess:
            user = sess.query(mUser).filter(mUser.github_id == github_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")
            if not is_user_active(user):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {github_id} is already inactive"
                )
            user.is_active = False
            sess.add(user)
            sess.commit()
            return serialize_user_for_requester(User.model_validate(user), requester)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/role", response_model=UserResponse, description="Set user a role")
async def set_user_role(
    github_id: int,
    role: Role,
    requester: Annotated[User, Depends(permissions.is_admin_or_superuser)],
) -> UserResponse:
    if role not in utils.get_roles():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role {role} not found")
    try:
        with get_sess() as sess:
            user = sess.query(mUser).filter(mUser.github_id == github_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")
            user.role = role
            sess.add(user)
            sess.commit()
            return serialize_user_for_requester(User.model_validate(user), requester)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/", response_model=UserResponse, description="Update user data")
async def update_user_data(
    github_id: int,
    payload: UserUpdatePayload,
    requester: Annotated[User, Depends(permissions.is_admin_or_superuser)],
) -> UserResponse:
    try:
        user = utils.get_user(github_id)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")
    try:
        for key, value in payload.items():
            setattr(user, key, value)
        return serialize_user_for_requester(utils.update_user(user), requester)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Bad request data. Details {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail=f"Invalid data. Details {str(e)}")


@router.get("/roles", response_model=list[str], description="Get all roles")
async def get_roles() -> list[str]:
    return utils.get_roles()


router_exposed = APIRouter(prefix="/users", dependencies=[Depends(auth_utils.get_current_user)])


@router_exposed.get("/me", response_model=User, description="Get current user data")
async def get_current_user_data(user: Annotated[User, Depends(auth_utils.get_current_user)]) -> User:
    try:
        return utils.get_user(user.github_id)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user.github_id} not found")
