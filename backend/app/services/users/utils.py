import json
from typing import Any

from app.core.config import settings
from app.db.database import get_sess
from app.db.models.user import Role
from app.db.models.user import User as mUser
from app.db.schemas.user import User, UserBase
from app.services.users.roles import add_role
from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError


def get_user(github_id: int) -> User:
    with get_sess() as sess:
        return User.model_validate(sess.query(mUser).filter(mUser.github_id == github_id).first())


def is_username_in_muid(username: str, muid: str) -> bool:
    if not username or not muid:
        return False
    return username == muid.split("-", 2)[2]


def check_creator_github_handle_in_list(username: str, item_list: list[dict]) -> bool:
    return username in [item["creator_github_handle"] for item in item_list]


def add_user_to_db(data: dict[str, str | int]) -> tuple[bool, UserBase | None]:
    if not data.get("github_id"):
        return False, None

    with get_sess() as sess:
        if sess.query(mUser).filter(mUser.github_id == data["github_id"]).first():
            return False, get_user(data["github_id"])

        sess.add(mUser(**add_role(data).model_dump()))
        sess.commit()

        return True, get_user(data["github_id"])


def update_user(user_data: User | dict[str, Any]) -> User:
    user_data: User = User.model_validate(user_data)
    try:
        with get_sess() as sess:
            user = sess.query(mUser).filter(mUser.github_id == user_data.github_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_data.github_id} not found"
                )
            for key, value in user_data.model_dump().items():
                setattr(user, key, value)
            sess.commit()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unique data conflict")
    return user_data


def is_user_active(user: UserBase) -> bool:
    return user.is_active


def get_roles() -> list[str]:
    return [role.value for role in Role]
