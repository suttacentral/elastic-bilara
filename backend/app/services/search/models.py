from pydantic import BaseModel


class SearchSegmentOut(BaseModel):
    results: dict[str, dict[str, str]]
