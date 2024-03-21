from pydantic import BaseModel


class SearchSegmentOut(BaseModel):
    results: dict[str, dict[str, str]]


class TranslationHintsOut(BaseModel):
    muid: str
    uid: str
    segment: str
    translation_hints: str
    strength: int
