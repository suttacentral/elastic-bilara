from pydantic import BaseModel, model_validator


class GitCommitInfoOut(BaseModel):
    git_recent_commits: list[dict]

class NotificationDoneOut(BaseModel):
    success: bool