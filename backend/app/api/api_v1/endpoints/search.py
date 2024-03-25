from typing import Annotated

from app.db.schemas.user import UserBase
from app.services.auth.utils import get_current_user
from app.services.search.models import SearchSegmentOut, TranslationHintsOut
from app.services.users.permissions import is_user_active
from fastapi import APIRouter, Depends, HTTPException, Request, status
from search.search import Search

router = APIRouter(prefix="/search")

es = Search()


@router.get(
    "/",
    description="This endpoint accepts any number of query parameters. Append them to the URL like this: ?muid1=value1&muid2=value2",  # noqa: 501
    response_model=SearchSegmentOut,
)
async def search(
    user: Annotated[UserBase, Depends(get_current_user)],
    request: Request,
    uid: str | None = None,
    size: int = 10,
    page: int = 0,
) -> SearchSegmentOut:
    params: dict[str, str] = {**request.query_params}
    size = int(params.pop("size", size))
    page = int(params.pop("page", page))
    uid = params.pop("uid", uid)
    if uid and not params:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least one muid",
        )
    if not params:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No query parameters provided",
        )
    params["uid"] = uid
    return SearchSegmentOut(results=es.get_segments(size, page, params))


@router.get("/hints/", response_model=list[TranslationHintsOut], dependencies=[Depends(is_user_active)])
async def get_translation_hints(
    source_muid: str, target_muid: str, segment_id: str, text_value: str
) -> list[TranslationHintsOut]:
    similar_phrases: list[dict] = es.get_phrase_similar_segments(text_value, source_muid)
    translation_hints = es.get_segment_value_for_uids_and_muid(
        [phrase_dict.get("uid") for phrase_dict in similar_phrases], target_muid
    )
    similar_phrases_with_translation = es.merge_segments_with_translation_hints(similar_phrases, translation_hints)
    translation_hints = es.aggregate_similar_segments(similar_phrases_with_translation)
    return [
        TranslationHintsOut(**hint)
        for hint in translation_hints
        if hint.get("uid") != segment_id and hint.get("translation_hints")
    ]
