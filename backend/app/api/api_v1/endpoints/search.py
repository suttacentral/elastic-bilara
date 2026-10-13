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
    source_muid: str | None = None,
    target_muid: str | None = None,
) -> SearchSegmentOut:
    params: dict[str, str] = {**request.query_params}
    size = int(params.pop("size", size))
    page = int(params.pop("page", page))
    uid = params.pop("uid", uid)
    params.pop("source_muid", None)
    params.pop("target_muid", None)
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
    for role, muid in (("source_muid", source_muid), ("target_muid", target_muid)):
        if muid is not None and muid not in params:
            raise HTTPException(status_code=400, detail=f"{role} must identify a selected project")
    params["uid"] = uid
    results = es.get_segments(size, page, params, source_muid=source_muid, target_muid=target_muid)
    return SearchSegmentOut(results=results, prefixes=es.get_segment_prefixes(results))


@router.get("/hints/", response_model=list[TranslationHintsOut], dependencies=[Depends(is_user_active)])
def get_translation_hints(
    source_muid: str, target_muid: str, segment_id: str, text_value: str
) -> list[TranslationHintsOut]:
    return [
        TranslationHintsOut(**hint)
        for hint in es.get_translation_hints(text_value, source_muid, target_muid, segment_id)
    ]
