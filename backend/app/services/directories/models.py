from pydantic import BaseModel


class FilesAndDirsOut(BaseModel):
    base: str | None = None
    directories: list[str] = []
    files: list[str] | None = None
