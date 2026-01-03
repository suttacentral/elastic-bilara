from pydantic import BaseModel, ConfigDict


class UserPreferenceBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    notification_authors: list[str]
    notification_days: int


class UserPreferenceUpdate(BaseModel):
    notification_authors: list[str]
    notification_days: int


class UserPreference(UserPreferenceBase):
    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    id: int
    github_id: int
