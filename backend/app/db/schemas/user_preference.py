from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserPreferenceBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    notification_authors: list[str]
    notification_days: int
    pali_lookup: bool = True
    dblclick_search: bool = True


class UserPreferenceUpdate(BaseModel):
    notification_authors: list[str]
    notification_days: int


class UserPreferenceSettingsUpdate(BaseModel):
    pali_lookup: Optional[bool] = None
    dblclick_search: Optional[bool] = None


class UserPreference(UserPreferenceBase):
    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    id: int
    github_id: int
