from pydantic import BaseModel


class FileWithProgress(BaseModel):
    """File information with translation progress"""
    name: str
    progress: float | None = None  # None = not calculated, -1 = error
    total_keys: int = 0
    translated_keys: int = 0


class FilesAndDirsOut(BaseModel):
    base: str | None = None
    directories: list[str] = []
    files: list[str] | None = None
    files_with_progress: list[FileWithProgress] | None = None
