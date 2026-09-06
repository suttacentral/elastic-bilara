from pydantic import BaseModel, Field


class FileWithProgress(BaseModel):
    """File information with translation progress"""
    name: str
    progress: float | None = None  # None = not calculated, -1 = error
    total_keys: int = 0
    translated_keys: int = 0


class VirtualFileOut(BaseModel):
    name: str
    target_path: str
    target_muid: str
    source_path: str
    source_muid: str
    prefix: str


class FilesAndDirsOut(BaseModel):
    base: str | None = None
    directories: list[str] = []
    files: list[str] | None = None
    files_with_progress: list[FileWithProgress] | None = None
    virtual_directories: list[str] = Field(default_factory=list)
    virtual_files: list[VirtualFileOut] = Field(default_factory=list)
