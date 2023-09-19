from pydantic import BaseModel, conlist


class PullRequestData(BaseModel):
    paths: conlist(str, min_length=1) = []
