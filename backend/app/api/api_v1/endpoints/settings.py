from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.db.database import get_sess
from app.services.auth import utils as auth_utils
from app.db.models.user_preference import UserPreference as UserPreferenceModel
from app.db.schemas.user_preference import (
    UserPreferenceSettingsUpdate,
)


class UserSettingsResponse(BaseModel):
    """Response schema for the settings endpoint (subset of user_preferences)."""
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    id: int
    github_id: int
    pali_lookup: bool = True
    dblclick_search: bool = True
    dblclick_search_collapse_inputs: bool = True
    hint_style: str = "dropdown"
    hint_count: int = 5


router = APIRouter(prefix="/settings")


def _to_bool(val, default=True):
    return val if val is not None else default


def _to_str(val, default="dropdown"):
    return val if isinstance(val, str) and val else default


def _to_int(val, default=5):
    return val if type(val) is int else default


@router.get("", response_model=UserSettingsResponse)
def get_user_settings(
    user: str = Depends(auth_utils.get_current_user),
):
    """Get user settings from user_preferences table. Returns defaults if not set."""
    with get_sess() as sess:
        row = (
            sess.query(UserPreferenceModel)
            .filter(UserPreferenceModel.github_id == user.github_id)
            .first()
        )

        if row:
            return UserSettingsResponse(
                id=row.id,
                github_id=row.github_id,
                pali_lookup=_to_bool(row.pali_lookup),
                dblclick_search=_to_bool(row.dblclick_search),
                dblclick_search_collapse_inputs=_to_bool(row.dblclick_search_collapse_inputs),
                hint_style=_to_str(row.hint_style),
                hint_count=_to_int(row.hint_count),
            )
        else:
            return UserSettingsResponse(
                id=0,
                github_id=user.github_id,
                pali_lookup=True,
                dblclick_search=True,
                dblclick_search_collapse_inputs=True,
                hint_style="dropdown",
                hint_count=5,
            )


@router.put("", response_model=UserSettingsResponse)
def update_user_settings(
    payload: UserPreferenceSettingsUpdate,
    user: str = Depends(auth_utils.get_current_user),
):
    """Update settings fields in user_preferences table (upsert)."""
    with get_sess() as sess:
        existing = (
            sess.query(UserPreferenceModel)
            .filter(UserPreferenceModel.github_id == user.github_id)
            .first()
        )

        if existing:
            if payload.pali_lookup is not None:
                existing.pali_lookup = payload.pali_lookup
            if payload.dblclick_search is not None:
                existing.dblclick_search = payload.dblclick_search
            if payload.dblclick_search_collapse_inputs is not None:
                existing.dblclick_search_collapse_inputs = payload.dblclick_search_collapse_inputs
            if payload.hint_style is not None:
                existing.hint_style = payload.hint_style
            if payload.hint_count is not None:
                existing.hint_count = payload.hint_count

            sess.commit()
            sess.refresh(existing)

            return UserSettingsResponse(
                id=existing.id,
                github_id=existing.github_id,
                pali_lookup=_to_bool(existing.pali_lookup),
                dblclick_search=_to_bool(existing.dblclick_search),
                dblclick_search_collapse_inputs=_to_bool(existing.dblclick_search_collapse_inputs),
                hint_style=_to_str(existing.hint_style),
                hint_count=_to_int(existing.hint_count),
            )
        else:
            new_pref = UserPreferenceModel(
                github_id=user.github_id,
                pali_lookup=_to_bool(payload.pali_lookup),
                dblclick_search=_to_bool(payload.dblclick_search),
                dblclick_search_collapse_inputs=_to_bool(payload.dblclick_search_collapse_inputs),
                hint_style=_to_str(payload.hint_style),
                hint_count=_to_int(payload.hint_count),
            )
            sess.add(new_pref)
            sess.commit()
            sess.refresh(new_pref)

            return UserSettingsResponse(
                id=new_pref.id,
                github_id=new_pref.github_id,
                pali_lookup=_to_bool(new_pref.pali_lookup),
                dblclick_search=_to_bool(new_pref.dblclick_search),
                dblclick_search_collapse_inputs=_to_bool(new_pref.dblclick_search_collapse_inputs),
                hint_style=_to_str(new_pref.hint_style),
                hint_count=_to_int(new_pref.hint_count),
            )
