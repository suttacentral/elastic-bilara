from pydantic import BaseModel


class GitCommitInfoOut(BaseModel):
    git_recent_commits: list[dict]


class NotificationFeedOut(BaseModel):
    notifications: list[dict]


class NotificationDoneOut(BaseModel):
    success: bool


class NotificationDonePayload(BaseModel):
    notification_type: str
    notification_ref: str
