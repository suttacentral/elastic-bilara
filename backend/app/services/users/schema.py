from pydantic import BaseModel, EmailStr


class UserData(BaseModel):
    github_id: int
    username: str
    email: EmailStr
    avatar_url: str
    role: str = "proofreader"
