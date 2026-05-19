from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DictionaryNoteCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    note_value: str = Field(max_length=10000)


class DictionaryNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    word: str
    note_value: str
    github_id: int
    created_at: datetime
    updated_at: datetime
