import json

from app.core.config import settings
from app.db.database import get_sess
from app.db.models.user import User as mUser
from app.db.schemas.user import User, UserBase
from app.services.users.roles import add_role
from fastapi import Depends
from search.utils import get_json_data
from sqlalchemy.orm import Session


def get_user(github_id: int) -> User:
    with get_sess() as sess:
        return User.model_validate(sess.query(mUser).filter(mUser.github_id == github_id).first())


def is_username_in_muid(username: str, muid: str) -> bool:
    if not username or not muid:
        return False
    return username == muid.split("-", 2)[2]


def check_creator_github_handle_in_list(username: str, item_list: list[dict]) -> bool:
    return username in [item["creator_github_handle"] for item in item_list]


def add_user_to_users_json(data: dict[str, str | int]) -> tuple[bool, UserBase | None]:
    if not data.get("github_id"):
        return False, None

    with get_sess() as sess:
        if sess.query(mUser).filter(mUser.github_id == data["github_id"]).first():
            return False, get_user(data["github_id"])

        sess.add(mUser(**add_role(data).model_dump()))
        sess.commit()

        return True, get_user(data["github_id"])
