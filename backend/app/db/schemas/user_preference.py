from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserPreferenceBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    notification_authors: list[str]
    notification_days: int
    pali_lookup: bool = True
    dblclick_search: bool = True
    dblclick_search_collapse_inputs: bool = True
    hint_style: str = "dropdown"
    hint_count: int = 5


class UserPreferenceUpdate(BaseModel):
    notification_authors: list[str]
    notification_days: int


class UserPreferenceSettingsUpdate(BaseModel):
    pali_lookup: Optional[bool] = None
    dblclick_search: Optional[bool] = None
    dblclick_search_collapse_inputs: Optional[bool] = None
    hint_style: Optional[str] = None
    hint_count: Optional[int] = Field(default=None, ge=1, le=20)


class UserPreference(UserPreferenceBase):
    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    id: int
    github_id: int
