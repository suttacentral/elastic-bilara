from typing import Annotated

from app.services.auth.utils import get_current_user
from app.services.search.models import SearchSegmentOut
from app.services.users.schema import UserData
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
    user: Annotated[UserData, Depends(get_current_user)],
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
