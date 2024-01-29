from typing import Annotated, Any, Optional

from app.db.database import get_sess
from app.db.models.user import User as mUser
from app.db.schemas.user import User, UserBase
from app.services.auth import utils as auth_utils
from app.services.users import utils
from app.services.users.utils import is_user_active
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic_core import ValidationError

router = APIRouter(prefix="/users")


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[User], description="Get all users")
async def get_users() -> list[User]:
    with get_sess() as sess:
        users = sess.query(mUser).all()
        return [User.model_validate(user) for user in users]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=User, description="Create a new user")
async def create_user(user: UserBase) -> User:
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
            return User.model_validate(sess.query(mUser).filter(mUser.github_id == user.github_id).first())
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


@router.get("/{github_id}/", response_model=User, description="Get a user")
async def get_user(github_id: int) -> User:
    try:
        return utils.get_user(github_id)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.get("/{github_id}/is_active", response_model=bool, description="Check if a user is active")
async def get_user_is_active(github_id: int) -> bool:
    try:
        return is_user_active(utils.get_user(github_id))
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/activate", response_model=User, description="Activate a user")
async def activate_user(github_id: int) -> User:
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
            return User.model_validate(user)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/deactivate", response_model=User, description="Deactivate a user")
async def deactivate_user(github_id: int) -> User:
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
            return User.model_validate(user)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/role", response_model=User, description="Set user a role")
async def set_user_role(github_id: int, role: str) -> User:
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
            return User.model_validate(user)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {github_id} not found")


@router.patch("/{github_id}/", response_model=User, description="Update user data")
async def update_user_data(github_id: int, payload: dict[str, Any]) -> User:
    try:
        user = utils.get_user(github_id)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        for key, value in payload.items():
            setattr(user, key, value)
        return utils.update_user(user)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request data")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail="Invalid data")


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
